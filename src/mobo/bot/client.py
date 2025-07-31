"""Discord client implementation using LangGraph agent."""

import logging
from typing import Any
import discord
import io

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

                response = await self.message_handler.handle_message(
                    message, self.client.user
                )

                if response:
                    # Show typing indicator while preparing response
                    async with message.channel.typing():
                        try:
                            # Handle files if any
                            files: list[discord.File] = []
                            bytesio_objects: list[io.BytesIO] = (
                                []
                            )  # Track BytesIO objects for cleanup

                            if response.has_files() and response.files is not None:
                                for bot_file in response.files:
                                    discord_file: discord.File
                                    if isinstance(bot_file.content, io.BytesIO):
                                        discord_file = discord.File(
                                            bot_file.content, filename=bot_file.filename
                                        )
                                        bytesio_objects.append(bot_file.content)
                                    else:
                                        bio: io.BytesIO = io.BytesIO(bot_file.content)
                                        discord_file = discord.File(
                                            bio,
                                            filename=bot_file.filename,
                                        )
                                        bytesio_objects.append(bio)
                                    files.append(discord_file)

                            # Send the response with any files
                            try:
                                if files:
                                    await message.reply(response.text, files=files)
                                else:
                                    await message.reply(response.text)
                            finally:
                                # Ensure BytesIO objects are properly closed
                                for bio in bytesio_objects:
                                    bio.close()

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
