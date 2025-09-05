"""
SQLAlchemy models for the bot's memory system.

This module defines the database schema for conversation storage,
user profiles, and vector embeddings for RAG functionality.
"""

import uuid
from datetime import datetime, timedelta, UTC

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Float,
    Boolean,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

# Create base class for all models
Base = declarative_base()


class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps."""

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


# =============================================================================
# CONVERSATION MEMORY MODELS
# =============================================================================


class Conversation(Base, TimestampMixin):
    """
    Stores individual conversation messages for RAG retrieval.

    Each message (user or assistant) gets stored with its embedding
    for semantic similarity search.
    """

    __tablename__ = "conversations"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Message identification
    user_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False, index=True)
    guild_id = Column(String, nullable=True, index=True)  # None for DMs

    # Message content
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # Vector embedding for RAG (1536 dimensions for OpenAI embeddings)
    embedding = Column(Vector(1536), nullable=True)

    # Metadata
    message_length = Column(Integer, nullable=False, default=0)
    tokens_used = Column(Integer, nullable=True)  # Estimated tokens
    model_used = Column(
        String, nullable=True
    )  # Which model generated this (for assistant messages)

    # Additional context
    message_metadata = Column(JSON, nullable=True)  # Store additional context as JSON

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_conversations_user_channel", "user_id", "channel_id"),
        Index("idx_conversations_guild_time", "guild_id", "created_at"),
        Index("idx_conversations_role_time", "role", "created_at"),
        # Vector similarity index (created separately in initialize_database)
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, role={self.role}, user_id={self.user_id})>"


class ConversationSummary(Base, TimestampMixin):
    """
    Stores periodic summaries of conversations for long-term context.

    When conversations get very long, we can summarize chunks and store
    the summaries for efficient context retrieval.
    """

    __tablename__ = "conversation_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What this summary covers
    channel_id = Column(String, nullable=False, index=True)
    guild_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)  # None for multi-user summaries

    # Time range this summary covers
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    # Summary content
    summary = Column(Text, nullable=False)
    summary_embedding = Column(Vector(1536), nullable=True)

    # Metadata
    message_count = Column(Integer, nullable=False, default=0)
    summary_type = Column(
        String, nullable=False, default="conversation"
    )  # 'conversation', 'user_behavior', etc.

    __table_args__ = (
        Index("idx_summaries_channel_time", "channel_id", "start_time", "end_time"),
    )


# =============================================================================
# USER PROFILE MODELS
# =============================================================================


class User(Base, TimestampMixin):
    """
    Core user information and profile data.
    """

    __tablename__ = "users"

    # Use Discord user ID as primary key
    discord_user_id = Column(String, primary_key=True)

    # Basic user info
    display_name = Column(String, nullable=False)
    username = Column(String, nullable=True)  # Discord username
    discriminator = Column(String, nullable=True)  # Discord discriminator (legacy)
    avatar_url = Column(String, nullable=True)

    # Bot interaction settings
    response_tone = Column(
        String, nullable=False, default="neutral"
    )  # How bot should respond: friendly, neutral, hostile, etc.
    interaction_count = Column(Integer, nullable=False, default=0)
    last_seen = Column(DateTime, nullable=True)

    # Preferences and settings
    preferred_language = Column(String, nullable=True, default="en")
    timezone = Column(String, nullable=True)

    # Relationships
    likes = relationship(
        "UserLike", back_populates="user", cascade="all, delete-orphan"
    )
    dislikes = relationship(
        "UserDislike", back_populates="user", cascade="all, delete-orphan"
    )
    aliases = relationship(
        "UserAlias", back_populates="user", cascade="all, delete-orphan"
    )

    # Additional data
    custom_data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<User(discord_user_id={self.discord_user_id}, display_name={self.display_name})>"


class UserLike(Base, TimestampMixin):
    """Things a user likes or enjoys."""

    __tablename__ = "user_likes"

    id = Column(Integer, primary_key=True)

    # Foreign key to user
    user_id = Column(
        String, ForeignKey("users.discord_user_id", ondelete="CASCADE"), nullable=False
    )

    # What they like
    like_term = Column(String, nullable=False)
    confidence = Column(
        Float, nullable=False, default=1.0
    )  # How confident we are (0.0-1.0)
    source = Column(
        String, nullable=True
    )  # How we learned this ('explicit', 'inferred', etc.)

    # Relationships
    user = relationship("User", back_populates="likes")

    __table_args__ = (
        Index("idx_user_likes_user", "user_id"),
        Index("idx_user_likes_term", "like_term"),
        # Unique constraint to prevent duplicates
        Index("idx_user_likes_unique", "user_id", "like_term", unique=True),
    )


class UserDislike(Base, TimestampMixin):
    """Things a user dislikes or wants to avoid."""

    __tablename__ = "user_dislikes"

    id = Column(Integer, primary_key=True)

    # Foreign key to user
    user_id = Column(
        String, ForeignKey("users.discord_user_id", ondelete="CASCADE"), nullable=False
    )

    # What they dislike
    dislike_term = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    source = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="dislikes")

    __table_args__ = (
        Index("idx_user_dislikes_user", "user_id"),
        Index("idx_user_dislikes_term", "dislike_term"),
        Index("idx_user_dislikes_unique", "user_id", "dislike_term", unique=True),
    )


class UserAlias(Base, TimestampMixin):
    """Alternative names or nicknames a user prefers."""

    __tablename__ = "user_aliases"

    id = Column(Integer, primary_key=True)

    # Foreign key to user
    user_id = Column(
        String, ForeignKey("users.discord_user_id", ondelete="CASCADE"), nullable=False
    )

    # Alias information
    alias = Column(String, nullable=False)
    is_preferred = Column(
        Boolean, nullable=False, default=False
    )  # Is this their preferred name?
    source = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="aliases")

    __table_args__ = (
        Index("idx_user_aliases_user", "user_id"),
        Index("idx_user_aliases_alias", "alias"),
        Index("idx_user_aliases_unique", "user_id", "alias", unique=True),
    )


# =============================================================================
# BOT INTERACTION TRACKING
# =============================================================================


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


# =============================================================================
# ANALYTICS AND INSIGHTS
# =============================================================================


class ConversationAnalytics(Base, TimestampMixin):
    """
    Analytics data about conversations and user interactions.
    """

    __tablename__ = "conversation_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What this analytics record covers
    date = Column(DateTime, nullable=False, index=True)  # Date this data is for
    guild_id = Column(String, nullable=True, index=True)
    channel_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)

    # Conversation metrics
    message_count = Column(Integer, nullable=False, default=0)
    user_message_count = Column(Integer, nullable=False, default=0)
    bot_response_count = Column(Integer, nullable=False, default=0)

    # Response metrics
    avg_response_time = Column(Float, nullable=True)  # Average response time in seconds
    total_tokens_used = Column(Integer, nullable=False, default=0)
    total_api_calls = Column(Integer, nullable=False, default=0)

    # Tool usage
    tools_used = Column(JSON, nullable=True)  # {"tool_name": count, ...}
    images_generated = Column(Integer, nullable=False, default=0)
    gifs_searched = Column(Integer, nullable=False, default=0)

    # User satisfaction (if we implement feedback)
    positive_reactions = Column(Integer, nullable=False, default=0)
    negative_reactions = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_analytics_date_guild", "date", "guild_id"),
        Index("idx_analytics_date_user", "date", "user_id"),
    )


# =============================================================================
# RATE LIMITING
# =============================================================================


class RateLimit(Base, TimestampMixin):
    """
    Tracks API usage for rate limiting across different resources.

    This allows multiple tools to share rate limits for the same underlying
    resource (e.g., multiple tools using Google Search API).
    """

    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True)

    # Resource identification
    resource_name = Column(String, nullable=False, index=True)  # e.g., 'google-search'
    period_start = Column(
        DateTime, nullable=False, index=True
    )  # Start of current period
    period_end = Column(DateTime, nullable=False, index=True)  # End of current period

    # Usage tracking
    current_usage = Column(Integer, nullable=False, default=0)
    max_usage = Column(Integer, nullable=False)  # Maximum allowed in this period

    # Optional user-specific rate limiting
    user_id = Column(String, nullable=True, index=True)  # None for global limits

    # Metadata
    period_type = Column(
        String, nullable=False, default="day"
    )  # 'minute', 'hour', 'day', 'month'

    __table_args__ = (
        Index(
            "idx_rate_limits_resource_period",
            "resource_name",
            "period_start",
            "period_end",
        ),
        Index("idx_rate_limits_resource_user", "resource_name", "user_id"),
        # Unique constraint to prevent duplicate periods
        Index(
            "idx_rate_limits_unique",
            "resource_name",
            "period_start",
            "user_id",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<RateLimit(resource={self.resource_name}, usage={self.current_usage}/{self.max_usage})>"

    def is_exceeded(self, increment: int = 1) -> bool:
        """Check if the rate limit has been or would be exceeded."""
        return self.current_usage + increment > self.max_usage

    def can_make_requests(self, count: int = 1) -> bool:
        """Check if we can make the specified number of requests."""
        return (self.current_usage + count) <= self.max_usage

    def remaining_requests(self) -> int:
        """Get the number of remaining requests in this period."""
        return max(0, self.max_usage - self.current_usage)

    def time_until_reset(self) -> timedelta:
        """Get time until this rate limit period resets."""
        now = datetime.now(UTC)
        if now >= self.period_end:
            return timedelta(0)
        return self.period_end - now

    @classmethod
    def get_period_bounds(
        cls, period_type: str, base_time: datetime = None
    ) -> tuple[datetime, datetime]:
        """
        Get the start and end times for a rate limit period.

        Args:
            period_type: Type of period ('minute', 'hour', 'day', 'month')
            base_time: Base time to calculate from (defaults to now)

        Returns:
            Tuple of (period_start, period_end)
        """
        if base_time is None:
            base_time = datetime.now(UTC)

        if period_type == "minute":
            start = base_time.replace(second=0, microsecond=0)
            end = start + timedelta(minutes=1)
        elif period_type == "hour":
            start = base_time.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period_type == "day":
            start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period_type == "month":
            # First day of current month
            start = base_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # First day of next month
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:
            raise ValueError(f"Invalid period type: {period_type}")

        return start, end


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_tables_if_not_exist(engine):
    """
    Create all tables if they don't exist.

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(engine)


async def create_tables_async(engine):
    """
    Create all tables asynchronously.

    Args:
        engine: Async SQLAlchemy engine
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_conversation_by_id(session, conversation_id: str):
    """
    Get a conversation by ID.

    Args:
        session: SQLAlchemy session
        conversation_id: Conversation UUID

    Returns:
        Conversation object or None
    """
    return (
        session.query(Conversation).filter(Conversation.id == conversation_id).first()
    )


def get_user_by_discord_id(session, discord_user_id: str):
    """
    Get a user by their Discord user ID.

    Args:
        session: SQLAlchemy session
        discord_user_id: Discord user ID as string

    Returns:
        User object or None
    """
    return session.query(User).filter(User.discord_user_id == discord_user_id).first()


def get_recent_conversations(session, channel_id: str, limit: int = 10):
    """
    Get recent conversations from a channel.

    Args:
        session: SQLAlchemy session
        channel_id: Discord channel ID
        limit: Maximum number of conversations to return

    Returns:
        List of Conversation objects
    """
    return (
        session.query(Conversation)
        .filter(Conversation.channel_id == channel_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )


# =============================================================================
# MODEL VALIDATION
# =============================================================================


def validate_conversation_data(data: dict) -> tuple[bool, str]:
    """
    Validate conversation data before insertion.

    Args:
        data: Dictionary containing conversation data

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["user_id", "channel_id", "role", "content"]

    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"

    if data["role"] not in ["user", "assistant"]:
        return False, f"Invalid role: {data['role']}"

    if len(data["content"]) > 10000:  # Reasonable limit
        return False, "Content too long"

    return True, ""


def validate_user_data(data: dict) -> tuple[bool, str]:
    """
    Validate user data before insertion.

    Args:
        data: Dictionary containing user data

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["discord_user_id", "display_name"]

    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"

    # Validate Discord user ID format (should be numeric string)
    try:
        int(data["discord_user_id"])
    except ValueError:
        return False, "Invalid Discord user ID format"

    return True, ""
