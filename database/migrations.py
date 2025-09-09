"""Database migration utilities"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from database.models import Base
from shared.config import settings

logger = logging.getLogger(__name__)

async def create_tables():
    """Create all database tables"""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    logger.info("Database tables created")

async def drop_tables():
    """Drop all database tables"""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    logger.info("Database tables dropped")

if __name__ == "__main__":
    asyncio.run(create_tables())