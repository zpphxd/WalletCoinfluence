#!/usr/bin/env python3
"""Send paper trading update to Telegram on demand."""

import asyncio
from src.scheduler.hourly_report import send_hourly_update

if __name__ == "__main__":
    asyncio.run(send_hourly_update())
