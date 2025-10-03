"""Main scheduler entry point."""

import logging
import asyncio
from src.scheduler.jobs import setup_scheduler
from src.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the scheduler."""
    logger.info("Starting Alpha Wallet Scout Worker")

    scheduler = setup_scheduler()
    scheduler.start()

    logger.info("Scheduler started. Press Ctrl+C to exit.")

    try:
        # Keep the scheduler running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour at a time
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
