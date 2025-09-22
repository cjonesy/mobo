"""
User profile models for the mobo bot.

This module defines the database schema for user profiles,
preferences, likes, dislikes, and aliases.
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from mobo.db import Base
from mobo.models.base import TimestampMixin


class User(Base, TimestampMixin):
    """
    Core user information and profile data.
    """

    __tablename__ = "users"

    # Use Discord user ID as primary key
    discord_user_id = Column(String, primary_key=True)

    # Bot interaction settings
    response_tone = Column(
        String, nullable=False, default="neutral"
    )  # How bot should respond: friendly, neutral, hostile, etc.
    last_seen = Column(DateTime(timezone=True), nullable=True)

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

    def __repr__(self):
        return f"<User(discord_user_id={self.discord_user_id})>"


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
