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

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bot.config import get_settings, validate_required_settings
from bot.memory.langgraph_memory import LangGraphMemory
from bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database initialization and setup using modern LangGraph patterns."""

    def __init__(self):
        self.settings = get_settings()
        self.memory_system = None

    async def initialize_all(self):
        """Initialize LangGraph memory system."""
        logger.info("🗄️ Starting LangGraph database initialization...")

        try:
            # Initialize LangGraph memory system (handles both checkpointing and user profiles)
            logger.info("🚀 Initializing LangGraph memory system...")
            self.memory_system = LangGraphMemory(
                database_url=self.settings.database_url,
                openai_api_key=self.settings.openai_api_key.get_secret_value(),
            )
            await self.memory_system.initialize()
            logger.info("✅ LangGraph memory system initialized")

            logger.info("🎉 Database initialization completed successfully!")

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up database connections."""
        if self.memory_system:
            await self.memory_system.close()

    async def verify_setup(self):
        """Verify that the LangGraph memory system is properly set up."""
        logger.info("🔍 Verifying LangGraph setup...")

        try:
            # Test LangGraph memory system
            self.memory_system = LangGraphMemory(
                database_url=self.settings.database_url,
                openai_api_key=self.settings.openai_api_key.get_secret_value(),
            )
            await self.memory_system.initialize()

            # Test user profile functionality
            test_profile = await self.memory_system.get_user_profile("test_user")

            if not test_profile:
                raise RuntimeError("Failed to retrieve test user profile")

            logger.info("✅ User profile functionality verified")

            # Test thread ID generation
            thread_id = self.memory_system.get_thread_id("test_channel")
            if not thread_id:
                raise RuntimeError("Failed to generate thread ID")

            logger.info("✅ Thread management verified")
            logger.info("🎉 LangGraph verification completed successfully!")

        except Exception as e:
            logger.error(f"❌ LangGraph verification failed: {e}")
            raise
        finally:
            await self.cleanup()

    def print_database_info(self):
        """Print information about the database configuration."""
        print("\n📊 Database Configuration:")
        print(f"  URL: {self.settings.database_url}")
        print(f"  Type: PostgreSQL")
        print(f"  Echo: {self.settings.database_echo}")

        if self.settings.is_postgresql():
            print(f"  Pool Size: {self.settings.database_pool_size}")
            print(f"  Max Overflow: {self.settings.database_max_overflow}")

        print()


async def main():
    """Main initialization function."""
    # Setup logging
    setup_logging()
    logger.info("🚀 Database initialization script started")

    try:
        # Validate configuration
        validate_required_settings()
        logger.info("✅ Configuration validated")

        # Create initializer
        initializer = DatabaseInitializer()
        initializer.print_database_info()

        # Initialize database
        await initializer.initialize_all()

        # Verify setup
        await initializer.verify_setup()

        print("\n🎉 Database initialization completed successfully!")
        print("You can now run the bot with: uv run bot")

    except KeyboardInterrupt:
        logger.info("🛑 Database initialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Database initialization failed: {e}")
        sys.exit(1)


def create_database_only():
    """Create LangGraph database setup without verification (faster for development)."""

    async def _create():
        setup_logging()
        logger.info("🏗️ Setting up LangGraph database...")

        settings = get_settings()

        # Initialize LangGraph memory system
        memory_system = LangGraphMemory(settings.database_url)
        await memory_system.initialize()
        await memory_system.close()

        logger.info("✅ LangGraph database setup completed")

    asyncio.run(_create())


def reset_database():
    """Reset the database (WARNING: This will delete all data!)."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from bot.memory.models import Base

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

        engine = create_async_engine(settings.database_url)

        try:
            async with engine.begin() as conn:
                # Drop all tables
                await conn.run_sync(Base.metadata.drop_all)
                logger.info("🗑️ All tables dropped")

                # Recreate all tables
                await conn.run_sync(Base.metadata.create_all)
                logger.info("🏗️ All tables recreated")

            logger.info("✅ Database reset completed")

        finally:
            await engine.dispose()

    asyncio.run(_reset())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        "--verify-only", action="store_true", help="Only verify existing database setup"
    )
    parser.add_argument(
        "--create-only",
        action="store_true",
        help="Only create tables, skip verification",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (WARNING: Deletes all data!)",
    )

    args = parser.parse_args()

    if args.reset:
        reset_database()
    elif args.create_only:
        create_database_only()
    elif args.verify_only:

        async def verify_only():
            setup_logging()
            initializer = DatabaseInitializer()
            await initializer.verify_setup()

        asyncio.run(verify_only())
    else:
        asyncio.run(main())
