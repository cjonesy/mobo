"""
Main Discord client implementation.

This handles Discord events and routes messages through the LangGraph workflow,
managing the connection between Discord and the bot's core logic.
"""

import logging
from typing import Optional

import discord

from ..config import Settings
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
        intents.presences = True

        super().__init__(intents=intents)

        self.settings = settings
        self.workflow = None
        self.message_processor: Optional[MessageProcessor] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.admin_handler: Optional[AdminHandler] = None

        logger.info("🤖 Discord client initialized")

    async def initialize(self):
        """Initialize all components."""
        logger.info("🔧 Initializing Discord client components...")

        try:
            logger.info("🔑 Logging in to Discord...")
            await self.login(self.settings.discord.token.get_secret_value())

            logger.info(
                "🔧 Storing database configuration for per-message workflows..."
            )
            # Store database URL for creating workflows per message
            self.database_url = self.settings.database.url_for_langgraph

            processing_context = ProcessingContext(
                database_url=self.database_url,
                bot_user=self.user,
                client=self,
            )

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
    # BOT OPERATIONS
    # =============================================================================

    async def set_activity(
        self, activity_type: str = "playing", activity_name: str = ""
    ):
        """
        Change the bot's activity status.

        Args:
            activity_type: Type of activity - "playing", "listening", "watching",
                          "competing", "streaming", or "custom"
            activity_name: What specifically the bot is doing
        """
        try:
            if activity_name.strip():
                activity_map = {
                    "playing": discord.ActivityType.playing,
                    "listening": discord.ActivityType.listening,
                    "watching": discord.ActivityType.watching,
                    "competing": discord.ActivityType.competing,
                    "streaming": discord.ActivityType.streaming,
                    "custom": discord.ActivityType.custom,
                }

                activity_type_lower = activity_type.lower()
                if activity_type_lower not in activity_map:
                    logger.error(f"❌ Invalid activity type: {activity_type}")
                    raise ValueError(f"Invalid activity type: {activity_type}")

                activity = discord.Activity(
                    type=activity_map[activity_type_lower], name=activity_name.strip()
                )

                logger.info(f"🎭 Setting bot activity: {activity_type} {activity_name}")
                await self.change_presence(activity=activity)
            else:
                logger.info("🎭 Clearing bot activity")
                await self.change_presence(activity=None)

            logger.info("✅ Bot activity updated successfully")

        except Exception as e:
            logger.error(f"❌ Failed to change bot activity: {e}")
            raise ValueError(f"Failed to change bot activity: {e}")

    async def add_reaction_to_message(self, message: discord.Message, emoji: str):
        """
        Add a reaction to a Discord message.

        Args:
            message: The Discord message to react to
            emoji: The emoji to add (can be Unicode emoji or custom emoji name)
        """
        try:
            # Try to add the reaction directly first (works for Unicode emoji)
            await message.add_reaction(emoji)
            logger.info(f"✅ Added reaction {emoji} to message")
        except discord.NotFound:
            # If that fails, try to find custom emoji in the guild
            if hasattr(message, "guild") and message.guild:
                custom_emoji = discord.utils.get(message.guild.emojis, name=emoji)
                if custom_emoji:
                    await message.add_reaction(custom_emoji)
                    logger.info(f"✅ Added custom reaction {emoji} to message")
                else:
                    logger.error(f"❌ Emoji {emoji} not found")
                    raise ValueError(f"Emoji {emoji} not found")
            else:
                logger.error(f"❌ Failed to add reaction {emoji}")
                raise ValueError(f"Failed to add reaction {emoji}")
        except Exception as e:
            logger.error(f"❌ Failed to add reaction {emoji}: {e}")
            raise ValueError(f"Failed to add reaction: {e}")

    async def create_poll_in_channel(
        self,
        channel: discord.TextChannel,
        question: str,
        options: list[str],
        duration_hours: int = 24,
    ):
        """
        Create a poll in a Discord channel.

        Args:
            channel: The Discord channel to create the poll in
            question: The poll question
            options: List of poll options
            duration_hours: How long the poll should run
        """
        try:
            from datetime import timedelta

            # Validate inputs (Discord API constraints)
            if len(options) < 2:
                raise ValueError("Polls need at least 2 options")
            if len(options) > 10:
                raise ValueError("Polls can have maximum 10 options")
            if duration_hours < 1 or duration_hours > 168:
                raise ValueError(
                    "Poll duration must be between 1 and 168 hours (1 week)"
                )
            if len(question) > 300:
                raise ValueError("Poll question must be under 300 characters")

            # Create the poll object
            poll = discord.Poll(
                question=question,
                duration=timedelta(hours=duration_hours),
            )

            # Add options (Discord limits to 10 options, truncate long options)
            for option in options[:10]:
                if len(option) > 55:
                    option = option[:52] + "..."
                poll.add_answer(text=option)

            # Send the poll
            await channel.send(poll=poll)
            logger.info(f"✅ Poll created successfully with {len(options)} options")
        except Exception as e:
            logger.error(f"❌ Failed to create poll: {e}")
            raise ValueError(f"Failed to create poll: {e}")

    async def send_sticker_to_channel(
        self, channel: discord.TextChannel, sticker_name: str, message_content: str = ""
    ):
        """
        Send a sticker to a Discord channel.

        Args:
            channel: The Discord channel to send sticker to
            sticker_name: Name of the sticker to send (guild stickers only)
            message_content: Optional message text to include with the sticker

        Returns:
            Discord message object that was sent
        """
        try:
            sticker = None

            # First try to find the sticker in the guild (custom stickers)
            if hasattr(channel, "guild") and channel.guild:
                sticker = discord.utils.get(channel.guild.stickers, name=sticker_name)

            # If not found, try to find it by ID in guild stickers
            if not sticker:
                try:
                    sticker_id = int(sticker_name)
                    if hasattr(channel, "guild") and channel.guild:
                        sticker = discord.utils.get(
                            channel.guild.stickers, id=sticker_id
                        )
                except ValueError:
                    pass

            if not sticker:
                raise ValueError(f"Sticker '{sticker_name}' not found in this server")

            # Send the sticker
            sent_message = await channel.send(
                content=message_content or None, stickers=[sticker]
            )
            logger.info(f"✅ Sent sticker {sticker_name} to channel")
            return sent_message

        except Exception as e:
            logger.error(f"❌ Failed to send sticker {sticker_name}: {e}")
            raise ValueError(f"Failed to send sticker: {e}")

    async def get_user_profile(self, user_id: str, guild=None) -> dict:
        """
        Get detailed profile information for a Discord user.

        Args:
            user_id: The Discord user ID (string or int)
            guild: Optional guild context for member-specific info

        Returns:
            Dictionary with user profile information
        """
        try:
            # Convert string ID to int
            try:
                user_id_int = int(str(user_id).strip("<@>"))
            except ValueError:
                raise ValueError(f"Invalid user ID format: {user_id}")

            # Get user and member objects
            user = None
            member = None

            if guild:
                # Try to get as guild member first
                try:
                    member = guild.get_member(user_id_int)
                    if member:
                        user = member
                except (AttributeError, TypeError):
                    pass

            # If not found as member, try to fetch from client
            if not user:
                try:
                    user = await self.fetch_user(user_id_int)
                except (discord.NotFound, discord.HTTPException, AttributeError):
                    raise ValueError(
                        f"User with ID {user_id} not found or not accessible"
                    )

            if not user:
                raise ValueError(f"User with ID {user_id} not found or not accessible")

            # Build profile information
            profile = {
                "name": user.name,
                "id": str(user.id),
                "display_name": user.display_name,
                "global_name": user.global_name,
                "mention": user.mention,
                "bot": user.bot,
                "avatar_url": str(user.avatar.url) if user.avatar else None,
                "created_at": (
                    user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                    if user.created_at
                    else None
                ),
            }

            # Add guild-specific info if member
            if member and guild:
                profile.update(
                    {
                        "joined_at": (
                            member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                            if member.joined_at
                            else None
                        ),
                        "status": (
                            str(member.status) if hasattr(member, "status") else None
                        ),
                        "nickname": member.nick,
                    }
                )

                # Activity
                if hasattr(member, "activity") and member.activity:
                    activity_type = str(member.activity.type).replace(
                        "ActivityType.", ""
                    )
                    profile["activity"] = f"{activity_type} {member.activity.name}"
                else:
                    profile["activity"] = None

                # Roles
                if member.roles:
                    roles = [role for role in member.roles if role.name != "@everyone"]
                    if roles:
                        role_names = [
                            role.name
                            for role in sorted(
                                roles, key=lambda x: x.position, reverse=True
                            )
                        ]
                        profile["roles"] = role_names
                    else:
                        profile["roles"] = []
                else:
                    profile["roles"] = []
            else:
                profile.update(
                    {
                        "guild_name": None,
                        "joined_at": None,
                        "status": None,
                        "nickname": None,
                        "activity": None,
                        "roles": [],
                        "is_member": False,
                    }
                )

            logger.info(f"👤 Retrieved profile for user {user.name} ({user.id})")
            return profile

        except Exception as e:
            logger.error(f"❌ Failed to get user profile for {user_id}: {e}")
            raise ValueError(f"Failed to get user profile: {e}")
