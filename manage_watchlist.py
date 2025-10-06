#!/usr/bin/env python3
"""CLI tool for managing custom watchlist wallets."""

import sys
from src.api.watchlist import add_wallet_cli, list_wallets_cli, remove_wallet_cli

USAGE = """
🔍 CUSTOM WATCHLIST MANAGER

Usage:
  python manage_watchlist.py add <address> [chain] [label]
  python manage_watchlist.py list
  python manage_watchlist.py remove <address> [chain]

Examples:
  # Add a wallet to watch
  python manage_watchlist.py add 0x1234... ethereum "My favorite whale"

  # List all custom wallets
  python manage_watchlist.py list

  # Remove a wallet
  python manage_watchlist.py remove 0x1234... ethereum

Supported chains: ethereum, base, arbitrum, solana
"""


def main():
    """Run CLI commands."""
    if len(sys.argv) < 2:
        print(USAGE)
        return

    command = sys.argv[1].lower()

    if command == "add":
        if len(sys.argv) < 3:
            print("❌ Error: Address required")
            print(USAGE)
            return

        address = sys.argv[2]
        chain = sys.argv[3] if len(sys.argv) > 3 else "ethereum"
        label = sys.argv[4] if len(sys.argv) > 4 else None

        add_wallet_cli(address, chain, label)

    elif command == "list":
        list_wallets_cli()

    elif command == "remove":
        if len(sys.argv) < 3:
            print("❌ Error: Address required")
            print(USAGE)
            return

        address = sys.argv[2]
        chain = sys.argv[3] if len(sys.argv) > 3 else "ethereum"

        remove_wallet_cli(address, chain)

    else:
        print(f"❌ Unknown command: {command}")
        print(USAGE)


if __name__ == "__main__":
    main()
