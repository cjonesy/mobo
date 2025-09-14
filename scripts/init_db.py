#!/usr/bin/env python3
"""
Database initialization script.

This script initializes the database schema, creates tables, and sets up
the necessary extensions (like pgvector for PostgreSQL).
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to the Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from mobo.config import get_settings, Settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore
from mobo.utils.logging import setup_logging
from mobo.db import get_engine, Base, get_session_maker

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database initialization and setup using modern LangGraph patterns."""

    def __init__(self):
        self.settings: Settings = get_settings()
        self.session_maker = get_session_maker()

    async def initialize_all(self):
        """Initialize database schema and LangGraph memory system."""
        logger.info("🗄️ Starting database initialization...")

        try:
            # Create all application tables
            logger.info("🏗️ Creating application tables...")
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Application tables created")

            # Initialize LangGraph components using proper context managers
            logger.info("🚀 Initializing LangGraph components...")
            async with AsyncPostgresSaver.from_conn_string(
                self.settings.database.url_for_langgraph
            ) as checkpointer:
                await checkpointer.setup()
                logger.info("✅ AsyncPostgresSaver schema initialized")

            with PostgresStore.from_conn_string(
                self.settings.database.url_for_langgraph
            ) as store:
                store.setup()
                logger.info("✅ PostgresStore schema initialized")

            logger.info("🎉 Database initialization completed successfully!")

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    def print_database_info(self):
        """Print information about the database configuration."""
        print("\n📊 Database Configuration:")
        print(f"  URL: {self.settings.database.url}")
        print(f"  Type: PostgreSQL")
        print(f"  Echo: {self.settings.database.echo}")

        if "postgresql" in self.settings.database.url.lower():
            print(f"  Pool Size: {self.settings.database.pool_size}")
            print(f"  Max Overflow: {self.settings.database.max_overflow}")

        print()


async def main():
    """Main initialization function."""
    # Setup logging
    setup_logging()
    logger.info("🚀 Database initialization script started")

    try:
        # Create initializer
        initializer = DatabaseInitializer()
        initializer.print_database_info()

        # Initialize database
        await initializer.initialize_all()

        print("\n🎉 Database initialization completed successfully!")
        print("You can now run the bot with: uv run bot")

    except KeyboardInterrupt:
        logger.info("🛑 Database initialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Database initialization failed: {e}")
        sys.exit(1)


def reset_database():
    """Reset the database (WARNING: This will delete all data!)."""

    async def _reset():
        setup_logging()
        settings = get_settings()

        # Confirm deletion
        print("⚠️  WARNING: This will delete ALL data in the database!")
        response = input("Are you sure you want to continue? (type 'yes' to confirm): ")

        if response.lower() != "yes":
            print("❌ Database reset cancelled")
            return

        logger.info("🗑️ Resetting database...")

        async with get_engine().begin() as conn:
            # Drop all tables
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("🗑️ All tables dropped")

            # Recreate all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("🏗️ All tables recreated")

        logger.info("✅ Database reset completed")

    asyncio.run(_reset())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (WARNING: Deletes all data!)",
    )

    args = parser.parse_args()

    if args.reset:
        reset_database()
    else:
        asyncio.run(main())
