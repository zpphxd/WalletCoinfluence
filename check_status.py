#!/usr/bin/env python3
"""Check paper trading status (console output, no Telegram)."""

import json
import os
import subprocess
from datetime import datetime

def check_status():
    """Print current paper trading status to console."""

    # Try to read from Docker container first
    try:
        result = subprocess.run(
            ["/Applications/Docker.app/Contents/Resources/bin/docker", "exec", "wallet_scout_worker",
             "cat", "/app/paper_trading_log.json"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
        else:
            raise Exception("Container file not found")
    except:
        # Fallback to local file
        log_file = "paper_trading_log.json"
        if not os.path.exists(log_file):
            print("📊 No paper trading data yet. Waiting for first confluence signal...")
            return

        with open(log_file) as f:
            data = json.load(f)

    # Calculate stats
    starting_balance = data.get("starting_balance", 1000.0)
    current_balance = data.get("current_balance", starting_balance)
    positions = data.get("positions", {})
    closed_trades = data.get("closed_trades", [])
    total_profit = data.get("total_profit", 0.0)
    total_loss = data.get("total_loss", 0.0)
    win_count = data.get("win_count", 0)
    loss_count = data.get("loss_count", 0)
    last_updated = data.get("last_updated", "Unknown")

    total_trades = len(closed_trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    roi = ((current_balance - starting_balance) / starting_balance) * 100

    # Print report
    print("\n" + "="*70)
    print("📊 ALPHA WALLET SCOUT - PAPER TRADING STATUS")
    print("="*70)
    print()
    print(f"💰 BALANCE: ${current_balance:,.2f}")
    print(f"   Started: ${starting_balance:,.2f}")
    print(f"   ROI: {roi:+.2f}%")
    print()
    print(f"📈 TRADES: {total_trades} total ({win_count}W / {loss_count}L)")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Total Profit: ${total_profit:,.2f}")
    print(f"   Total Loss: ${total_loss:,.2f}")
    print()
    print(f"📍 OPEN POSITIONS: {len(positions)}")

    if positions:
        print()
        print("🔓 OPEN:")
        for token_addr, pos in list(positions.items())[:5]:
            token_display = f"{token_addr[:8]}...{token_addr[-6:]}"
            entry = pos['entry_price']
            cost = pos['cost_basis']
            print(f"  • {token_display}: ${cost:.2f} @ ${entry:.8f}")

    if closed_trades:
        print()
        print("🔒 RECENT CLOSED:")
        for trade in closed_trades[-5:]:
            token_display = f"{trade['token_address'][:8]}..."
            profit_pct = trade['profit_pct']
            profit_loss = trade['profit_loss']
            emoji = "✅" if profit_loss > 0 else "❌"
            print(f"  {emoji} {token_display}: {profit_pct:+.1f}% (${profit_loss:+.2f})")

    print()
    print(f"🕒 Last Updated: {last_updated}")
    print("="*70)
    print()

if __name__ == "__main__":
    check_status()
