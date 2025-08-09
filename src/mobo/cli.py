"""Command line interface for the LangGraph Discord bot."""

import asyncio
import logging
import sys
from typing import Any

import click

from .bot.client import DiscordBot
from .config import get_config, Config


def setup_logging(log_level: str) -> None:
    """Set up logging configuration."""
    level: int = getattr(logging, log_level.upper(), logging.INFO)

    # Import colorlog for colored output
    import colorlog

    # Configure colored logging format
    formatter = colorlog.ColoredFormatter(
        "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)-32s%(reset)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    # Console handler
    console_handler: logging.StreamHandler[Any] = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(console_handler)

    # Set specific loggers
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """LangChain Discord Bot CLI."""
    ctx.ensure_object(dict)
    config = get_config()
    setup_logging(config.log_level)


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the Discord bot."""
    config: Config = get_config()

    # Validate configuration
    if not config.discord_token.get_secret_value():
        click.echo("❌ Error: DISCORD_TOKEN environment variable is required", err=True)
        sys.exit(1)

    if not config.openai_api_key.get_secret_value():
        click.echo(
            "❌ Error: OPENAI_API_KEY environment variable is required", err=True
        )
        sys.exit(1)

    if not config.openrouter_api_key.get_secret_value():
        click.echo(
            "❌ Error: OPENROUTER_API_KEY environment variable is required", err=True
        )
        sys.exit(1)

    # Check personality prompt
    try:
        config.get_resolved_personality_prompt_sync()
    except Exception as e:
        click.echo(f"❌ Error: Personality prompt configuration invalid: {e}", err=True)
        sys.exit(1)

    click.echo("🤖 Starting LangGraph Discord Bot...")
    click.echo(f"📊 Database: {config.database_url}")
    click.echo(f"🧠 Model: {config.openai_model}")
    click.echo(f"🎭 Max bot responses: {config.max_bot_responses}")

    # Create and run bot
    bot: DiscordBot = DiscordBot()

    try:
        bot.run()
    except KeyboardInterrupt:
        click.echo("\n🛑 Bot stopped by user")
    except Exception as e:
        click.echo(f"❌ Bot crashed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def check_config(ctx: click.Context) -> None:
    """Check configuration and dependencies."""
    click.echo("🔍 Checking configuration...")

    try:
        config: Config = get_config()

        # Check required environment variables
        issues: list[str] = []

        if not config.discord_token.get_secret_value():
            issues.append("❌ DISCORD_TOKEN not set")
        else:
            click.echo("✅ Discord token configured")

        if not config.openai_api_key.get_secret_value():
            issues.append("❌ OPENAI_API_KEY not set")
        else:
            click.echo("✅ OpenAI API key configured")

        # Check personality prompt
        try:
            personality: str = config.get_resolved_personality_prompt_sync()
            click.echo(f"✅ Personality prompt loaded ({len(personality)} characters)")
        except Exception as e:
            issues.append(f"❌ Personality prompt error: {e}")

        # Check database URL format
        if "postgresql" not in config.database_url:
            issues.append("❌ Database URL should be PostgreSQL")
        else:
            click.echo("✅ Database URL format valid")

        # Summary
        if issues:
            click.echo("\n❌ Configuration issues found:")
            for issue in issues:
                click.echo(f"   {issue}")
            sys.exit(1)
        else:
            click.echo("\n✅ Configuration looks good!")

    except Exception as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def init_db(ctx: click.Context) -> None:
    """Initialize the database schema."""

    async def _init_db() -> None:
        click.echo("🗄️ Initializing database...")

        try:
            from .memory import RAGMemory
            from .agent.user_profiles import UserProfileManager
            from .agent.bot_interaction_tracker import BotInteractionTracker

            # Initialize all database components
            rag_memory: RAGMemory = RAGMemory()
            await rag_memory.initialize_database()
            await rag_memory.close()

            user_profiles: UserProfileManager = UserProfileManager()
            await user_profiles.initialize_database()
            await user_profiles.close()

            bot_tracker: BotInteractionTracker = BotInteractionTracker()
            await bot_tracker.initialize_database()
            await bot_tracker.close()

            click.echo("✅ Database initialized successfully!")

        except Exception as e:
            click.echo(f"❌ Database initialization failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_init_db())


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
