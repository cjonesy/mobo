"""
Database models for PydanticAI Discord bot memory system.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]


class Base(DeclarativeBase):
    pass


class User(Base):
    """User table for storing Discord user profiles."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    conversation_style: Mapped[str] = mapped_column(
        String(50), nullable=False, default="friendly"
    )
    topics_of_interest: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=[]
    )
    topics_disliked: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=[]
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    total_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consecutive_bot_responses: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_bot_interaction: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_users_user_id", "user_id"),
        Index("idx_users_last_active", "last_active"),
    )


class Conversation(Base):
    """Channel-wide conversation sessions."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    channel_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    embeddings: Mapped[List["MessageEmbedding"]] = relationship(
        "MessageEmbedding", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_conversations_channel_id", "channel_id"),
        Index("idx_conversations_updated_at", "updated_at"),
    )


class Message(Base):
    """Individual messages in conversations."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    content: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # Store PydanticAI ModelMessage as JSON
    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'user', 'assistant', 'system', etc.
    user_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # Discord user ID for user messages, None for assistant messages
    username: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Username stored at message creation time
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
        Index("idx_messages_user_id", "user_id"),
        Index("idx_messages_username", "username"),
    )


class MessageEmbedding(Base):
    """Embeddings for semantic search of message content."""

    __tablename__ = "message_embeddings"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="embeddings"
    )

    __table_args__ = (
        Index("idx_conversation_id_emb", "conversation_id"),
        Index("idx_created_at_emb", "created_at"),
    )


class ImageUsage(Base):
    """Track image generation usage for rate limiting."""

    __tablename__ = "image_usage"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=True
    )  # Optional user tracking
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_created_at_usage", "created_at"),
        Index("idx_tool_name", "tool_name"),
    )


# Pydantic models for validation and serialization


class UserProfile(BaseModel):
    """Pydantic model for user profile validation."""

    user_id: str
    username: str = ""
    conversation_style: str = "friendly"
    topics_of_interest: List[str] = Field(default_factory=list)
    topics_disliked: List[str] = Field(default_factory=list)
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_messages: int = 0
    is_bot: bool = False
    consecutive_bot_responses: int = 0
    last_bot_interaction: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Config:
        from_attributes = True


class ConversationInfo(BaseModel):
    """Pydantic model for conversation information."""

    user_id: str
    channel_id: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = None

    class Config:
        from_attributes = True


class MessageEmbeddingInfo(BaseModel):
    """Pydantic model for message embedding information."""

    content: str
    embedding: List[float]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        from_attributes = True
