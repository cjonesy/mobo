"""
Bot interaction service for anti-loop protection business logic.

This service handles all bot interaction tracking and anti-loop protection logic,
coordinating with the BotInteractionRepository to provide high-level operations
for managing bot-to-bot interactions in Discord channels.
"""

import logging
from typing import Tuple, Optional
from datetime import datetime, UTC, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import BotInteractionRepository

logger = logging.getLogger(__name__)


class BotInteractionService:
    """Service for bot interaction tracking and anti-loop protection."""

    def __init__(self):
        self.bot_interaction_repo = BotInteractionRepository()

    async def track_bot_interaction(
        self,
        session: AsyncSession,
        bot_user_id: str,
        channel_id: str,
        guild_id: Optional[str] = None,
        bot_name: Optional[str] = None,
        interaction_type: str = "message",
    ) -> int:
        """
        Track an interaction with another bot and return the current count.

        Args:
            session: Database session
            bot_user_id: Discord user ID of the bot we're interacting with
            channel_id: Discord channel ID
            guild_id: Discord guild ID (optional for DMs)
            bot_name: Optional bot display name
            interaction_type: Type of interaction

        Returns:
            Current interaction count with this bot in this channel
        """
        try:
            interaction = await self.bot_interaction_repo.get_or_create_interaction(
                session=session,
                bot_user_id=bot_user_id,
                channel_id=channel_id,
                guild_id=guild_id,
                bot_name=bot_name,
                interaction_type=interaction_type,
                last_interaction=datetime.now(UTC),
                interaction_count=0,
                is_currently_active=True,
            )

            interaction = await self.bot_interaction_repo.update_interaction(
                session=session,
                interaction=interaction,
                interaction_count=interaction.interaction_count + 1,
                last_interaction=datetime.now(UTC),
                is_currently_active=True,
                bot_name=(
                    bot_name if bot_name and interaction.bot_name != bot_name else None
                ),
            )

            await session.commit()

            logger.debug(
                f"Tracked interaction with bot {bot_user_id} in channel {channel_id}. "
                f"Count: {interaction.interaction_count}"
            )

            return interaction.interaction_count

        except Exception as e:
            logger.error(f"Error tracking bot interaction: {e}")
            await session.rollback()
            return 0

    async def should_respond_to_bot(
        self,
        session: AsyncSession,
        bot_user_id: str,
        channel_id: str,
        cooldown_seconds: int = 60,
        max_bot_responses: int = 5,
    ) -> Tuple[bool, int, str]:
        """
        Determine if we should respond to another bot based on anti-loop protection rules.

        Args:
            session: Database session
            bot_user_id: Discord user ID of the bot
            channel_id: Discord channel ID
            cooldown_seconds: Seconds to wait after hitting response limit before responding again (0 = no cooldown)
            max_bot_responses: Maximum consecutive responses before stopping (0 = unlimited)

        Returns:
            Tuple of (should_respond, current_count, reason)
        """
        try:
            # Try to get existing interaction record (don't create if it doesn't exist)
            from sqlalchemy import select

            stmt = select(self.bot_interaction_repo.model).where(
                self.bot_interaction_repo.model.bot_user_id == bot_user_id,
                self.bot_interaction_repo.model.channel_id == channel_id,
                self.bot_interaction_repo.model.is_currently_active,
            )
            result = await session.execute(stmt)
            interaction = result.scalar_one_or_none()

            if not interaction:
                return True, 0, "No previous interactions"

            # Check if we've exceeded the maximum consecutive responses
            if max_bot_responses > 0 and interaction.interaction_count >= max_bot_responses:
                # We've hit the limit - check if cooldown has expired
                if cooldown_seconds > 0:
                    time_since_last = (
                        datetime.now(UTC) - interaction.last_interaction
                    ).total_seconds()

                    if time_since_last >= cooldown_seconds:
                        # Cooldown expired - reset the interaction count
                        interaction.interaction_count = 0
                        interaction.is_currently_active = True
                        await session.commit()
                        logger.info(
                            f"🔄 Bot interaction cooldown expired for {bot_user_id} in {channel_id}, resetting count"
                        )
                        return True, 0, "Cooldown expired after hitting limit, interactions reset"

                # Still in cooldown or no cooldown configured but limit reached
                logger.info(
                    f"🚫 Bot interaction limit reached for {bot_user_id} in {channel_id}: "
                    f"{interaction.interaction_count}/{max_bot_responses} consecutive responses"
                )
                return (
                    False,
                    int(interaction.interaction_count),
                    f"Max consecutive responses exceeded ({interaction.interaction_count}/{max_bot_responses})",
                )

            return True, int(interaction.interaction_count), "Within limits"

        except Exception as e:
            logger.error(f"Error checking bot response eligibility: {e}")
            # Default to allowing response on error to avoid breaking functionality
            return True, 0, "Error occurred, allowing response"

    async def cleanup_old_interactions(
        self, session: AsyncSession, older_than_days: int = 7
    ) -> int:
        """
        Clean up old bot interaction records.

        Args:
            session: Database session
            older_than_days: Delete interactions older than this many days

        Returns:
            Number of records cleaned up
        """
        try:
            cutoff_time = datetime.now(UTC) - timedelta(days=older_than_days)

            count = await self.bot_interaction_repo.delete_interactions_before(
                session=session,
                cutoff_time=cutoff_time,
                exclude_active=True,
            )

            if count > 0:
                await session.commit()
                logger.info(f"Cleaned up {count} old bot interaction records")

            return count

        except Exception as e:
            logger.error(f"Error cleaning up old interactions: {e}")
            await session.rollback()
            return 0
