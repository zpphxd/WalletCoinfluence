#!/usr/bin/env python3
"""Monitor PEPE position in real-time."""

import asyncio
import sys
from datetime import datetime

async def monitor():
    """Monitor PEPE position."""

    # Import inside function to avoid module issues
    from src.utils.price_fetcher import MultiSourcePriceFetcher
    from src.analytics.paper_trading import PaperTradingTracker

    fetcher = MultiSourcePriceFetcher()

    # Position details
    entry_price = 0.00001009
    qty = 19821605.550049555
    cost_basis = 200.0

    # Sell triggers
    take_profit_price = entry_price * 1.20  # +20%
    stop_loss_price = entry_price * 0.90    # -10%

    print("\n" + "="*70)
    print("🐸 PEPE POSITION MONITOR")
    print("="*70)
    print(f"Entry Price: ${entry_price:.8f}")
    print(f"Quantity: {qty:,.0f} PEPE")
    print(f"Cost Basis: ${cost_basis:.2f}")
    print()
    print(f"📈 Take Profit: ${take_profit_price:.8f} (+20%)")
    print(f"📉 Stop Loss: ${stop_loss_price:.8f} (-10%)")
    print("="*70)
    print()

    while True:
        try:
            # Get current price
            current_price = await fetcher.get_token_price(
                '0x6982508145454ce325ddbe47a25d4ec3d2311933',
                'ethereum'
            )

            # Calculate P/L
            current_value = qty * current_price
            profit_loss = current_value - cost_basis
            profit_pct = (profit_loss / cost_basis) * 100
            price_change_pct = ((current_price - entry_price) / entry_price) * 100

            # Determine status
            if current_price >= take_profit_price:
                status = "🚀 TAKE PROFIT TRIGGERED"
            elif current_price <= stop_loss_price:
                status = "⚠️ STOP LOSS TRIGGERED"
            elif profit_pct > 0:
                status = "✅ IN PROFIT"
            elif profit_pct < 0:
                status = "❌ IN LOSS"
            else:
                status = "⏸️ FLAT"

            # Print update
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {status}")
            print(f"  Price: ${current_price:.8f} ({price_change_pct:+.2f}%)")
            print(f"  Value: ${current_value:.2f} | P/L: ${profit_loss:+.2f} ({profit_pct:+.1f}%)")
            print()

            # Wait 30 seconds before next check
            await asyncio.sleep(30)

        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(monitor())
