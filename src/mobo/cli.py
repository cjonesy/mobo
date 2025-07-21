"""
Command-line interface for the Discord bot.
"""

import logging
import sys

from .utils.config import get_config
from .bot.client import client


def setup_logging():
    """Set up detailed logging configuration."""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set specific loggers to appropriate levels
    logger_levels = {
        "discord": logging.WARNING,
        "discord.http": logging.WARNING,
        "discord.gateway": logging.WARNING,
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
    }

    for logger_name, level in logger_levels.items():
        logging.getLogger(logger_name).setLevel(level)


def main():
    """Main entry point for the Discord bot."""
    print("🤖 Starting Discord Bot with PydanticAI...")

    # Set up logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    # Get and validate configuration
    try:
        config = get_config()
        logger.info("✅ Configuration loaded successfully")
        logger.info("🗄️  Using database-backed memory system")
    except Exception as e:
        logger.error(f"❌ Configuration loading failed: {e}")
        sys.exit(1)

    try:
        # Start the Discord bot
        logger.info("🚀 Starting Discord bot...")
        client.run(config.discord_token.get_secret_value())
    except KeyboardInterrupt:
        logger.info("👋 Received shutdown signal")
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("✅ Bot stopped successfully")


if __name__ == "__main__":
    main()
