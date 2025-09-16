"""
Main entry point for the Discord bot.
Handles startup, graceful shutdown, and error handling.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from mobo.config import settings
from mobo.discord.client import BotClient
from mobo.utils.logging import setup_logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore


class BotApplication:
    """Main application class that manages the bot lifecycle."""

    def __init__(self):
        self.settings = settings
        self.client: Optional[BotClient] = None
        self.logger = logging.getLogger(__name__)

    async def startup(self) -> None:
        """Initialize all bot components."""
        self.logger.info("🚀 Starting Discord bot...")

        try:
            self.logger.info("🤖 Initializing Discord client...")
            self.client = BotClient(settings=self.settings)
            await self.client.initialize()

            self.logger.info("✅ Bot startup complete!")

        except Exception as e:
            self.logger.error(f"❌ Failed to start bot: {e}")
            await self.cleanup()
            raise

    async def run(self):
        """Run the bot until interrupted."""
        await self.startup()

        try:
            await self.client.connect()

        except KeyboardInterrupt:
            self.logger.info("🛑 Received interrupt signal, shutting down...")
        except Exception as e:
            self.logger.error(f"❌ Bot crashed: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources on shutdown."""
        self.logger.info("🧹 Cleaning up resources...")

        try:
            if self.client:
                await self.client.cleanup()

            self.logger.info("✅ Cleanup complete!")

        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")


def setup_signal_handlers(app: BotApplication):
    """Setup graceful shutdown on SIGINT/SIGTERM."""

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        logging.getLogger(__name__).info(
            f"Received signal {signum}, initiating shutdown..."
        )
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        try:
            app = BotApplication()
            logger.info("✅ Configuration validated")
        except Exception as e:
            logger.error(f"❌ Configuration error: {e}")
            sys.exit(1)

        setup_signal_handlers(app)

        await app.run()

    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)


def sync_main():
    """Synchronous wrapper for main() - used by script entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


# Entry points
if __name__ == "__main__":
    sync_main()


def run_bot():
    """Entry point for `uv run bot`."""
    sync_main()


def run_dev():
    """Entry point for development with debug logging."""
    import os

    os.environ.setdefault("LOG_LEVEL", "DEBUG")
    sync_main()


def init_db():
    """Entry point for database initialization using modern LangGraph patterns."""

    async def _init():
        setup_logging()
        logger = logging.getLogger(__name__)

        try:
            logger.info("🗄️ Initializing LangGraph database schema...")

            async with AsyncPostgresSaver.from_conn_string(
                settings.database.url_for_langgraph
            ) as checkpointer:
                await checkpointer.setup()
                logger.info("✅ AsyncPostgresSaver schema initialized")

            with PostgresStore.from_conn_string(
                settings.database.url_for_langgraph
            ) as store:
                store.setup()
                logger.info("✅ PostgresStore schema initialized")

            logger.info("✅ LangGraph database initialized successfully!")

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    asyncio.run(_init())
