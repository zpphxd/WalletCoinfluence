"""Track complete whale portfolios - see EVERYTHING they're trading, not just seed tokens."""

import logging
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import Wallet, WalletStats30D, Trade
from src.clients.alchemy import AlchemyClient
import asyncio

logger = logging.getLogger(__name__)


async def track_whale_full_portfolios() -> None:
    """Track ALL tokens our profitable whales are trading (not just seed tokens).
    
    This discovers new alpha by seeing what whales trade that we haven't discovered yet.
    """
    db = SessionLocal()
    
    try:
        # Get our top profitable whales
        profitable_whales = (
            db.query(Wallet)
            .join(WalletStats30D, Wallet.address == WalletStats30D.wallet_address)
            .filter(WalletStats30D.unrealized_pnl_usd > 500)  # $500+ profit
            .limit(20)  # Top 20 whales
            .all()
        )
        
        logger.info(f"📊 Tracking full portfolios of {len(profitable_whales)} profitable whales")
        
        client = AlchemyClient()
        new_tokens_discovered = 0
        new_trades_found = 0
        
        for whale in profitable_whales:
            try:
                # Get ALL wallet transactions (not filtered by token)
                transactions = await client.get_wallet_transactions(
                    whale.address,
                    whale.chain_id,
                    limit=50  # Last 50 transactions
                )
                
                for tx in transactions:
                    token_address = tx.get("token_address")
                    
                    # Check if this is a NEW token we haven't seen
                    from src.db.models import Token
                    existing_token = db.query(Token).filter(
                        Token.token_address == token_address,
                        Token.chain_id == whale.chain_id
                    ).first()
                    
                    if not existing_token:
                        # NEW TOKEN discovered via whale portfolio!
                        logger.info(f"🆕 NEW TOKEN via whale {whale.address[:10]}...: {token_address[:10]}...")
                        new_tokens_discovered += 1
                        
                        # Add to tokens table
                        token = Token(
                            token_address=token_address,
                            chain_id=whale.chain_id,
                            symbol=tx.get("symbol", "UNKNOWN"),
                            last_price_usd=tx.get("price_usd", 0),
                            liquidity_usd=0,  # Will be updated by price fetcher
                        )
                        db.add(token)
                        db.flush()
                    
                    # Record the trade (if not already recorded)
                    tx_hash = tx.get("tx_hash")
                    existing_trade = db.query(Trade).filter(Trade.tx_hash == tx_hash).first()
                    
                    if not existing_trade:
                        trade = Trade(
                            tx_hash=tx_hash,
                            ts=tx.get("timestamp"),
                            chain_id=whale.chain_id,
                            wallet_address=whale.address,
                            token_address=token_address,
                            side=tx.get("type", "buy"),
                            qty_token=float(tx.get("amount", 0)),
                            price_usd=float(tx.get("price_usd", 0)),
                            usd_value=float(tx.get("value_usd", 0)),
                            venue=tx.get("dex"),
                        )
                        db.add(trade)
                        new_trades_found += 1
                
                db.commit()
                await asyncio.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error tracking whale {whale.address[:10]}...: {str(e)}")
                db.rollback()
                continue
        
        logger.info(
            f"✅ Whale portfolio tracking complete: "
            f"{new_tokens_discovered} new tokens, {new_trades_found} new trades"
        )
        
    except Exception as e:
        logger.error(f"Whale portfolio tracking failed: {str(e)}")
    finally:
        db.close()
