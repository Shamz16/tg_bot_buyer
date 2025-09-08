#!/usr/bin/env python3
"""Main startup script for Telegram Gift Buyer"""

import asyncio
import sys
import logging
from multiprocessing import Process

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_bot():
    """Run the Telegram bot UI"""
    import asyncio
    from bot.bot_main import main
    asyncio.run(main())


def run_buyer():
    """Run the buyer service"""
    import asyncio
    from buyer.buyer_service import main
    asyncio.run(main())


def main():
    """Start both services"""
    logger.info("Starting Telegram Gift Buyer System...")
    
    # Start bot process
    bot_process = Process(target=run_bot)
    bot_process.start()
    logger.info("Bot UI started")
    
    # Start buyer process
    buyer_process = Process(target=run_buyer)
    buyer_process.start()
    logger.info("Buyer service started")
    
    try:
        # Keep running
        bot_process.join()
        buyer_process.join()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bot_process.terminate()
        buyer_process.terminate()
        bot_process.join()
        buyer_process.join()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()