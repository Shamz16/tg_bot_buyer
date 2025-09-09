#!/usr/bin/env python3
"""Main startup script for Telegram Gift Buyer"""

import asyncio
import sys
import logging
from multiprocessing import Process
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_bot():
    """Run the Telegram bot UI"""
    try:
        import asyncio
        from bot.bot_main import main
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")


def run_buyer_api():
    """Run the buyer API server"""
    try:
        import asyncio
        from buyer.api_server import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        logger.error(f"Buyer API failed to start: {e}")


def main():
    """Start both services"""
    logger.info("Starting Telegram Gift Buyer System...")
    
    # Check if .env exists
    if not os.path.exists('.env'):
        logger.error("No .env file found. Please copy env.example to .env and configure it.")
        sys.exit(1)

    # Start bot process
    bot_process = Process(target=run_bot)
    bot_process.start()
    logger.info("Bot UI started")

    # Start buyer API process
    buyer_process = Process(target=run_buyer_api)
    buyer_process.start()
    logger.info("Buyer API server started")

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
