"""
Database migration utility for DataPilot.
Runs SQLAlchemy schema creation for all registered models.
"""

import asyncio
import sys
from app.db.session import engine
from app.core.config import settings
from app.core.logger import logger
from app.models import Base

async def run_migrations():
    logger.info("Running database migrations...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Successfully created/verified all tables: sources, collection_jobs, documents, workflows")
    except OSError as e:
        logger.error(
            f"Cannot connect to PostgreSQL at {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT} ({e}).\n"
            "Please ensure PostgreSQL is running:\n"
            "  1. Using Docker: Start Docker Desktop and run `docker compose up -d postgres` from project root.\n"
            "  2. Or using Homebrew: run `brew services start postgresql@15`"
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migrations())

