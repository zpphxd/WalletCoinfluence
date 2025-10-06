"""Automatic position management - take profits and cut losses."""

import logging
import asyncio
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.analytics.paper_trading import PaperTradingTracker
from src.utils.price_fetcher import MultiSourcePriceFetcher

logger = logging.getLogger(__name__)


async def manage_positions_job() -> None:
    """Check all open positions and sell if profit/loss targets hit.
    
    Runs every 5 minutes to actively manage positions.
    """
    db = SessionLocal()
    
    try:
        trader = PaperTradingTracker.load_from_file('/app/paper_trading_log.json')
        
        if not trader or not trader.positions:
            logger.info("No open positions to manage")
            return
        
        fetcher = MultiSourcePriceFetcher()
        sells_executed = 0
        
        logger.info(f"📊 Managing {len(trader.positions)} open positions")
        
        for token_addr, pos in list(trader.positions.items()):
            try:
                # Get current price
                current_price = await fetcher.get_token_price(token_addr, pos['chain_id'])
                
                if current_price == 0:
                    logger.warning(f"Cannot get price for {token_addr[:16]}..., skipping")
                    continue
                
                # Calculate P/L
                current_value = pos['qty'] * current_price
                profit_loss = current_value - pos['cost_basis']
                profit_pct = (profit_loss / pos['cost_basis']) * 100
                
                # SELL LOGIC - AGGRESSIVE COMPOUNDING STRATEGY
                should_sell = False
                reason = ''

                # 1. Take ANY profit at +5% or better (compound small wins!)
                if profit_pct >= 5:
                    should_sell = True
                    reason = f'TAKE PROFIT at +{profit_pct:.1f}% (compound & learn!)'

                # 2. Stop loss at -10% (cut losses fast)
                elif profit_pct <= -10:
                    should_sell = True
                    reason = f'STOP LOSS at {profit_pct:.1f}%'

                # 3. Free up capital if low on cash and position is down -5%+
                elif profit_pct <= -5 and trader.current_balance < 400:
                    should_sell = True
                    reason = f'FREE CAPITAL (balance low, {profit_pct:.1f}% loss)'
                
                if should_sell:
                    result = trader.execute_sell(token_addr, current_price, reason=reason)
                    
                    if result:
                        sells_executed += 1
                        emoji = '✅' if result['profit_loss'] > 0 else '❌'
                        logger.info(
                            f"{emoji} SOLD {token_addr[:16]}...: "
                            f"${result['profit_loss']:+.2f} ({result['profit_pct']:+.1f}%) - {reason}"
                        )
                        logger.info(f"   New balance: ${trader.current_balance:.2f}")
                        trader.save_to_file()
                else:
                    logger.debug(
                        f"⏸️  HOLDING {token_addr[:16]}...: "
                        f"${profit_loss:+.2f} ({profit_pct:+.1f}%)"
                    )
                
            except Exception as e:
                logger.error(f"Error managing position {token_addr[:16]}...: {str(e)}")
                continue
        
        if sells_executed > 0:
            logger.info(
                f"💰 Position management complete: {sells_executed} positions sold, "
                f"balance ${trader.current_balance:.2f}"
            )
        
    except Exception as e:
        logger.error(f"Position management job failed: {str(e)}")
    finally:
        db.close()
