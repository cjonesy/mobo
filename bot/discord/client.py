"""
Main Discord client implementation.

This handles Discord events and routes messages through the LangGraph workflow,
managing the connection between Discord and the bot's core logic.
"""

import logging
from typing import Optional

import discord

from ..config import Settings
from ..core.workflow import create_bot_workflow
from ..memory.langgraph_memory import LangGraphMemory
from .handlers import (
    MessageProcessor,
    ProcessingContext,
    ErrorHandler,
    AdminHandler,
)

logger = logging.getLogger(__name__)


class BotClient(discord.Client):
    """
    Main Discord client with LangGraph integration.

    This client handles Discord events, manages bot state, and routes messages
    through the LangGraph workflow for intelligent responses.
    """

    def __init__(self, settings: Settings):
        # Setup Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(intents=intents)

        self.settings = settings

        # Modern LangGraph memory system
        self.memory_system: Optional[LangGraphMemory] = None

        # Workflow (will be created after memory components are initialized)
        self.workflow = None

        # Statistics tracking
        self.stats = {"total_execution_time": 0.0}

        # Services (will be created after workflow is initialized)
        self.message_processor: Optional[MessageProcessor] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.admin_handler: Optional[AdminHandler] = None

        logger.info("🤖 Discord client initialized")

    async def initialize(self):
        """Initialize all components."""
        logger.info("🔧 Initializing Discord client components...")

        try:
            logger.info("🔑 Logging in to Discord...")
            await self.login(self.settings.discord_token.get_secret_value())

            logger.info("🚀 Initializing modern LangGraph memory system...")
            self.memory_system = LangGraphMemory(
                database_url=self.settings.database_url,
                openai_api_key=self.settings.openai_api_key.get_secret_value(),
            )
            await self.memory_system.initialize()

            logger.info("🛠️ Creating LangGraph workflow...")
            self.workflow = create_bot_workflow(
                settings=self.settings,
                memory_system=self.memory_system,
            )

            # Create callback for recording execution time
            def record_execution_time(time: float):
                self.stats["total_execution_time"] += time

            # Create processing context for message processor
            processing_context = ProcessingContext(
                workflow=self.workflow,
                bot_user=self.user,
                debug_mode=self.settings.debug_mode,
                record_execution_time=record_execution_time,
                client=self,
            )

            # Create services
            self.message_processor = MessageProcessor(processing_context)
            self.error_handler = ErrorHandler()
            self.admin_handler = AdminHandler(self.settings, self.error_handler)

            logger.info("✅ Discord client initialization complete")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Discord client: {e}")
            raise

    async def cleanup(self):
        """Clean up resources on shutdown."""
        logger.info("🧹 Cleaning up Discord client resources...")

        try:
            if not self.is_closed():
                await self.close()

            if self.memory_system:
                await self.memory_system.close()

            logger.info("✅ Discord client cleanup complete")

        except Exception as e:
            logger.error(f"❌ Error during Discord client cleanup: {e}")

    # =============================================================================
    # DISCORD EVENT HANDLERS
    # =============================================================================

    async def on_ready(self):
        """Called when bot successfully connects to Discord."""
        logger.info(f"🎉 {self.user} has connected to Discord!")
        logger.info(f"📊 Connected to {len(self.guilds)} guilds")
        logger.info(f"👥 Can see {len(set(self.get_all_members()))} total users")

        logger.info("✅ Bot is ready to process messages!")

    async def on_message(self, message: discord.Message):
        """Handle incoming Discord messages."""
        if not self.message_processor:
            logger.error("Message processor not initialized")
            return

        await self.message_processor.handle_message(message)

    async def on_error(self, event: str, *args, **kwargs):
        """Handle Discord client errors."""
        logger.error(f"Discord client error in {event}: {args} {kwargs}")

        if self.error_handler:
            await self.error_handler.handle_client_error(event, args, kwargs)

    async def on_guild_join(self, guild: discord.Guild):
        """Called when bot joins a new guild."""
        logger.info(f"🏰 Joined new guild: {guild.name} ({guild.id})")
        logger.info(f"👥 Guild has {guild.member_count} members")

    async def on_guild_remove(self, guild: discord.Guild):
        """Called when bot leaves a guild."""
        logger.info(f"👋 Left guild: {guild.name} ({guild.id})")

    async def on_member_join(self, member: discord.Member):
        """Called when a new member joins a guild."""
        logger.debug(f"👋 New member joined {member.guild.name}: {member.name}")

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

    async def change_bot_nickname(
        self, guild: discord.Guild, new_nickname: str
    ) -> bool:
        """
        Change the bot's nickname in a specific guild.

        Args:
            guild: The Discord guild
            new_nickname: New nickname to set

        Returns:
            True if successful, False otherwise
        """
        try:
            await guild.me.edit(nick=new_nickname)
            logger.info(f"✅ Changed nickname to '{new_nickname}' in {guild.name}")
            return True
        except discord.Forbidden:
            logger.warning(f"❌ No permission to change nickname in {guild.name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error changing nickname in {guild.name}: {e}")
            return False

    async def get_guild_from_channel(self, channel_id: str) -> Optional[discord.Guild]:
        """
        Get the guild associated with a channel ID.

        Args:
            channel_id: Discord channel ID

        Returns:
            Guild object or None if not found
        """
        try:
            channel = self.get_channel(int(channel_id))
            if channel and hasattr(channel, "guild"):
                return channel.guild
        except (ValueError, AttributeError, TypeError):
            pass
        return None
