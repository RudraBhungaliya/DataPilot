"""
Database migration entry point.

Delegates to Alembic so schema evolution is versioned and reproducible.

Usage:
    cd apps/server
    python -m app.db.migrate        # upgrade the database to the latest revision
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.logger import logger

SERVER_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    logger.info("Running database migrations (alembic upgrade head)...")
    cfg = Config(str(SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    try:
        command.upgrade(cfg, "head")
        logger.info("Database migrations applied successfully.")
    except Exception as e:
        logger.error(
            f"Migration failed: {e}\n"
            "Ensure PostgreSQL is running (docker compose up -d postgres)."
        )
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()
