#!/usr/bin/env python3
"""Quick test script to verify Telegram bot configuration."""

import asyncio
from telegram import Bot

# Your bot credentials
BOT_TOKEN = "8482390902:AAHFiGq9q9Gt-P7ErpZL0FDs9PyEYIwmN_c"
CHAT_ID = "8416972017"


async def test_telegram():
    """Send a test message to verify bot works."""
    print("🧪 Testing Telegram bot...")
    print(f"Bot Token: {BOT_TOKEN[:20]}...")
    print(f"Chat ID: {CHAT_ID}")
    print()

    try:
        bot = Bot(token=BOT_TOKEN)

        # Send test message
        message = """
🎉 *Alpha Wallet Scout Test Message*

✅ Your Telegram bot is working!

This is a test alert. Your bot configuration is correct and ready to send real alerts.

🚀 System will start sending real alerts in 2-4 hours after data collection begins.
        """

        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )

        print("✅ SUCCESS! Check your Telegram - you should see a test message!")
        print()
        print("Next steps:")
        print("1. Confirm you received the message in Telegram")
        print("2. Run: ./QUICKSTART.sh")
        print("3. Wait 2-4 hours for first real alerts")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()
        print("Troubleshooting:")
        print("1. Make sure you clicked START on @Alpha_Walletbot")
        print("2. Verify your Chat ID is correct")
        print("3. Check bot token is correct")


if __name__ == "__main__":
    asyncio.run(test_telegram())
