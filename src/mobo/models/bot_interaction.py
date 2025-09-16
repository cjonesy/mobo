"""
Bot interaction tracking models for the mobo bot.

This module defines the database schema for tracking interactions
with other bots for anti-loop protection.
"""

from datetime import datetime, UTC

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    Index,
)

from mobo.db import Base
from mobo.models.base import TimestampMixin


class BotInteraction(Base, TimestampMixin):
    """
    Tracks interactions with other bots for anti-loop protection.
    """

    __tablename__ = "bot_interactions"

    id = Column(Integer, primary_key=True)

    # Bot and location
    bot_user_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False, index=True)
    guild_id = Column(String, nullable=True, index=True)

    # Interaction tracking
    interaction_count = Column(Integer, nullable=False, default=0)
    last_interaction = Column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    is_currently_active = Column(Boolean, nullable=False, default=True)

    # Metadata
    bot_name = Column(String, nullable=True)
    interaction_type = Column(
        String, nullable=False, default="message"
    )  # 'message', 'reaction', etc.

    __table_args__ = (
        Index("idx_bot_interactions_bot_channel", "bot_user_id", "channel_id"),
        Index("idx_bot_interactions_active", "is_currently_active", "last_interaction"),
    )
