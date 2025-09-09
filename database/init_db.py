```

### 4. В коде есть ошибки импорта

```
# bot/bot_main.py

"""Initialize the database with all tables"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from database.models import Base
from shared.config import settings
from shared.logging_config import setup_logging

logger = setup_logging("init_db")

async def create_tables():
    """Create all database tables"""
    # Ensure the database directory exists
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    if db_path:
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    # Create database engine
    engine = create_async_engine(settings.database_url)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    logger.info("Database tables created successfully")

if __name__ == "__main__":
    asyncio.run(create_tables())