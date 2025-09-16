"""
Bot interaction repository for database operations.

This repository handles all database operations related to bot interaction tracking,
providing functionality for anti-loop protection and bot activity monitoring.
"""

from typing import Optional
from datetime import datetime

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .base import AsyncRepository
from ..models.bot_interaction import BotInteraction


class BotInteractionRepository(AsyncRepository[BotInteraction]):
    """Repository for BotInteraction model operations."""

    def __init__(self):
        super().__init__(BotInteraction)

    async def get_or_create_interaction(
        self,
        session: AsyncSession,
        bot_user_id: str,
        channel_id: str,
        guild_id: Optional[str] = None,
        bot_name: Optional[str] = None,
        interaction_type: str = "message",
        last_interaction: Optional[datetime] = None,
        interaction_count: int = 0,
        is_currently_active: bool = True,
    ) -> BotInteraction:
        """
        Get existing bot interaction or create a new one with provided values.

        Args:
            session: Database session
            bot_user_id: Discord bot user ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID (None for DMs)
            bot_name: Optional bot display name
            interaction_type: Type of interaction
            last_interaction: Timestamp for last interaction
            interaction_count: Initial interaction count
            is_currently_active: Whether interaction is currently active

        Returns:
            BotInteraction record
        """
        # Try to find existing interaction
        stmt = select(BotInteraction).where(
            BotInteraction.bot_user_id == bot_user_id,
            BotInteraction.channel_id == channel_id,
        )

        result = await session.execute(stmt)
        interaction = result.scalar_one_or_none()

        if interaction is None:
            # Create new interaction record with provided values
            interaction = BotInteraction(
                bot_user_id=bot_user_id,
                channel_id=channel_id,
                guild_id=guild_id,
                interaction_count=interaction_count,
                last_interaction=last_interaction,
                is_currently_active=is_currently_active,
                bot_name=bot_name,
                interaction_type=interaction_type,
            )
            session.add(interaction)
            await session.flush()

        return interaction

    async def update_interaction(
        self,
        session: AsyncSession,
        interaction: BotInteraction,
        interaction_count: Optional[int] = None,
        last_interaction: Optional[datetime] = None,
        is_currently_active: Optional[bool] = None,
        bot_name: Optional[str] = None,
    ) -> BotInteraction:
        """
        Update bot interaction with provided values.

        Args:
            session: Database session
            interaction: BotInteraction record to update
            interaction_count: New interaction count
            last_interaction: New timestamp
            is_currently_active: New active status
            bot_name: Updated bot name

        Returns:
            Updated BotInteraction record
        """
        if interaction_count is not None:
            interaction.interaction_count = interaction_count
        if last_interaction is not None:
            interaction.last_interaction = last_interaction
        if is_currently_active is not None:
            interaction.is_currently_active = is_currently_active
        if bot_name is not None:
            interaction.bot_name = bot_name

        await session.flush()
        return interaction

    async def delete_interactions_before(
        self,
        session: AsyncSession,
        cutoff_time: datetime,
        exclude_active: bool = False,
    ) -> int:
        """
        Delete bot interaction records before the given time.

        Args:
            session: Database session
            cutoff_time: Delete interactions before this time
            exclude_active: Whether to exclude currently active interactions

        Returns:
            Number of records deleted
        """
        conditions = [BotInteraction.last_interaction < cutoff_time]

        if exclude_active:
            conditions.append(BotInteraction.is_currently_active.is_(False))

        stmt = delete(BotInteraction).where(and_(*conditions))
        result = await session.execute(stmt)
        return result.rowcount or 0
