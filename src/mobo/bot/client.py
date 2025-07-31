"""Discord client implementation using LangGraph agent."""

import logging
import tempfile
from typing import Any
import discord
import httpx


from .message_handler import MessageHandler
from ..config import get_config, Config

logger = logging.getLogger(__name__)


class DiscordBot:
    """Main Discord bot client using LangGraph."""

    def __init__(self) -> None:
        self.config: Config = get_config()

        # Set up Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.client: discord.Client = discord.Client(intents=intents)
        self.message_handler: MessageHandler = MessageHandler()

        # Set up event handlers
        self._setup_events()

    def _setup_events(self) -> None:
        """Set up Discord event handlers."""

        @self.client.event
        async def on_ready() -> None:
            """Event handler for when the bot is ready."""
            if self.client.user:
                logger.info(f"🤖 {self.client.user} has connected to Discord!")

                try:
                    await self.message_handler.initialize()
                    logger.info("🧠 LangGraph agent initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize agent: {e}")

        @self.client.event
        async def on_message(message: discord.Message) -> None:
            """Event handler for incoming Discord messages."""
            try:
                # Handle the message through our message handler
                if self.client.user is None:
                    logger.error("Bot user is not available")
                    return

                async with message.channel.typing():
                    response = await self.message_handler.handle_message(
                        message, self.client.user
                    )

                    if response:
                        try:
                            files: list[discord.File] = []

                            if response.has_files() and response.files is not None:
                                for bot_file in response.files:
                                    async with httpx.AsyncClient() as client:
                                        file_response = await client.get(bot_file.url)
                                        if file_response.status_code == 200:
                                            temp_file = tempfile.NamedTemporaryFile(
                                                suffix=".png", delete=False
                                            )
                                            temp_file.write(file_response.content)
                                            temp_file.flush()
                                            discord_file = discord.File(temp_file.name)
                                            files.append(discord_file)

                                            # Store temp file for cleanup
                                            if not hasattr(response, "_temp_files"):
                                                response._temp_files = []
                                            response._temp_files.append(temp_file)
                            try:
                                if files:
                                    await message.reply(response.text, files=files)
                                else:
                                    await message.reply(response.text)
                            finally:
                                if hasattr(response, "_temp_files"):
                                    for tmp_file in response._temp_files:
                                        tmp_file.close()

                        except Exception as e:
                            logger.error(f"Error sending response: {e}")

            except Exception as e:
                logger.error(f"Error in on_message: {e}")

        @self.client.event
        async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
            """Event handler for Discord client errors."""
            logger.error(f"Discord client error in {event}: {args} {kwargs}")

    async def start(self) -> None:
        """Start the Discord bot."""
        try:
            logger.info("🚀 Starting Discord bot...")
            await self.client.start(self.config.discord_token.get_secret_value())
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise

    async def close(self) -> None:
        """Close the Discord bot and clean up resources."""
        logger.info("🛑 Shutting down Discord bot...")
        try:
            await self.message_handler.close()
            await self.client.close()
            logger.info("✅ Bot shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def run(self) -> None:
        """Run the Discord bot (blocking)."""
        try:
            self.client.run(self.config.discord_token.get_secret_value())
        except Exception as e:
            logger.error(f"Failed to run bot: {e}")
            raise
