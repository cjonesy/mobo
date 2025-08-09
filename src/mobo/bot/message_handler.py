"""Discord message handler with LangChain agent integration."""

import logging
from typing import Optional

import discord

from ..chains import DiscordAgent
from ..agent.bot_interaction_tracker import BotInteractionTracker
from ..config import get_config, Config
from ..agent.types import BotResponse

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles incoming Discord messages and routes them to the LangChain agent."""

    def __init__(self) -> None:
        self.config: Config = get_config()
        self.agent: DiscordAgent = DiscordAgent()
        self.bot_tracker: BotInteractionTracker = BotInteractionTracker()

    async def initialize(self) -> None:
        """Initialize the message handler and agent."""
        await self.agent.initialize()
        logger.info("Message handler initialized")

    async def should_respond(
        self, message: discord.Message, bot_user: discord.ClientUser | discord.User
    ) -> tuple[bool, str]:
        """
        Determine if the bot should respond to this message.

        Returns:
            Tuple of (should_respond, reason)
        """
        # Ignore messages from the bot itself
        if message.author == bot_user:
            return False, "Message from bot itself"

        # Ignore empty messages
        if not message.content.strip():
            return False, "Empty message"

        # Check if bot is mentioned directly
        bot_mentioned: bool = bot_user in message.mentions

        # Check if this is a reply to the bot
        is_reply_to_bot: bool = False
        if message.reference and message.reference.message_id:
            try:
                referenced_message: discord.Message = (
                    await message.channel.fetch_message(message.reference.message_id)
                )
                is_reply_to_bot = referenced_message.author == bot_user
            except discord.NotFound:
                # Referenced message not found, ignore
                pass
            except Exception as e:
                logger.error(f"Error fetching referenced message: {e}")

        # If not mentioned and not replying to bot, don't respond
        if not bot_mentioned and not is_reply_to_bot:
            return False, "Not mentioned and not a reply to bot"

        # Check bot interaction limits
        user_id: str = str(message.author.id)
        channel_id: str = str(message.channel.id)
        is_author_bot: bool = message.author.bot

        # Update bot interaction tracking
        await self.bot_tracker.update_bot_interaction(
            user_id, channel_id, is_author_bot
        )

        if is_author_bot:
            # Check if we can respond to this bot
            can_respond, reason = await self.bot_tracker.can_respond_to_bot(
                user_id, channel_id
            )
            if not can_respond:
                logger.info(
                    f"Bot interaction limit reached for {message.author.name} ({user_id}): {reason}"
                )
                return False, f"Bot limit: {reason}"
            else:
                logger.info(
                    f"Bot interaction allowed for {message.author.name} ({user_id}): {reason}"
                )
        else:
            # Human user - reset bot interaction counters for this channel
            await self.bot_tracker.reset_bot_interactions(channel_id)
            logger.info(
                f"Human user {message.author.name} joined conversation - reset bot counters"
            )

        return True, "Should respond"

    async def handle_message(
        self, message: discord.Message, bot_user: discord.ClientUser | discord.User
    ) -> Optional[BotResponse]:
        """
        Handle an incoming Discord message.

        Returns:
            BotResponse if the bot should respond, None otherwise
        """
        try:
            logger.info(
                f"Processing message from {message.author.name}: {message.content[:100]}"
            )

            # Extract message details
            user_id: str = str(message.author.id)
            channel_id: str = str(message.channel.id)
            guild_id: Optional[str] = str(message.guild.id) if message.guild else None
            user_message: str = message.content

            # Clean up the message content (remove mentions of the bot)
            cleaned_message: str = user_message
            for mention in message.mentions:
                if mention == bot_user:
                    cleaned_message = cleaned_message.replace(
                        f"<@{mention.id}>", ""
                    ).strip()
                    cleaned_message = cleaned_message.replace(
                        f"<@!{mention.id}>", ""
                    ).strip()

            # If the message is now empty after removing mentions, provide conversation context
            if not cleaned_message.strip():
                try:
                    # Get the last few messages from the channel for context
                    recent_messages: list[str] = []
                    async for msg in message.channel.history(limit=5, before=message):
                        if not msg.author.bot:  # Skip bot messages to avoid loops
                            recent_messages.append(
                                f"{msg.author.display_name}: {msg.content}"
                            )

                    if recent_messages:
                        # Reverse to get chronological order
                        recent_messages.reverse()
                        context: str = "\n".join(recent_messages)
                        cleaned_message = f"[System: User mentioned me with no message. Recent conversation context:]\n{context}"
                    else:
                        cleaned_message = "[System: User mentioned me with no message and no recent conversation context available]"

                except Exception as e:
                    logger.error(f"Error fetching conversation history: {e}")
                    cleaned_message = "[System: User mentioned me with no message, but couldn't retrieve conversation context]"

            # Process the message through the LangChain agent
            response: Optional[BotResponse] = await self.agent.process_message(
                user_message=cleaned_message,
                user_id=user_id,
                channel_id=channel_id,
                discord_client=message.guild.me if message.guild else None,
                guild_id=guild_id,
                client_user=bot_user,
            )

            logger.info(
                f"Generated response for {message.author.name}: {response.text[:100] if response else 'No response'}"
            )
            return response

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return None

    async def close(self) -> None:
        """Clean up resources."""
        await self.agent.close()
        await self.bot_tracker.close()
        logger.info("Message handler closed")
