"""
Memory system for PydanticAI Discord bot.

This module provides persistent memory storage with semantic search capabilities
using vector embeddings for intelligent conversation management.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from openai import AsyncOpenAI
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    UserPromptPart,
    TextPart,
)
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from .models import (
    Base,
    User,
    Conversation,
    Message,
    MessageEmbedding,
    UserProfile,
    MessageEmbeddingInfo,
    ImageUsage,
)

from ..utils.config import get_config

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Memory manager for PydanticAI Discord bot.

    Provides persistent storage of conversations, user profiles, and semantic search
    capabilities using vector embeddings.
    """

    def __init__(self):
        """Initialize the memory manager."""
        self.config = get_config()
        self.engine = create_async_engine(
            self.config.database_url,
            echo=self.config.database_echo,
            pool_size=self.config.database_pool_size,
            max_overflow=self.config.database_max_overflow,
        )
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.openai_client = AsyncOpenAI(
            api_key=self.config.openai_api_key.get_secret_value()
        )

    async def initialize_database(self):
        """Create database tables if they don't exist."""
        async with self.engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized with pgvector support")

    async def get_or_create_user(self, user_id: str, username: str) -> UserProfile:
        """Get existing user or create new one."""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    user_id=user_id,
                    username=username,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info(f"Created new user: {username} ({user_id})")
            else:
                current_username = getattr(user, "username", "")
                if current_username != username:
                    setattr(user, "username", username)
                    setattr(user, "last_active", datetime.now(timezone.utc))
                    await session.commit()
                    logger.info(f"Updated username for user {user_id}: {username}")

            return UserProfile.model_validate(user)

    async def start_conversation(self, user_id: str, channel_id: str) -> str:
        """Get existing conversation or create new one and return conversation ID."""
        session_id = f"{user_id}:{channel_id}"

        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if user is None:
                user = User(user_id=user_id, username="")
                session.add(user)
                await session.flush()

            conversation_result = await session.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            conversation = conversation_result.scalar_one_or_none()

            if conversation is None:
                conversation = Conversation(
                    session_id=session_id,
                    user_id=user.id,
                    channel_id=channel_id,
                )
                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)
                logger.info(
                    f"Started new conversation {conversation.id} for user {user_id}"
                )
            else:
                logger.info(
                    f"Using existing conversation {conversation.id} for user {user_id}"
                )

            return str(conversation.id)

    async def add_message(
        self,
        conversation_id: str,
        content: ModelMessage,
        message_type: str = "user",
        metadata: Optional[dict] = None,
    ) -> str:
        """Add a message to the conversation."""
        async with self.async_session() as session:
            try:
                message_json_str = ModelMessagesTypeAdapter.dump_json([content])
                message_json = json.loads(message_json_str)[0]
            except Exception as e:
                logger.error(f"Error serializing message: {e}")
                message_json = {
                    "content": str(content),
                    "type": type(content).__name__,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            message = Message(
                conversation_id=conversation_id,
                content=message_json,
                message_type=message_type,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            text_content = self._extract_text_from_message(content)
            if text_content:
                await self._generate_and_store_embedding(
                    session, str(message.id), text_content, conversation_id
                )

            await session.commit()
            logger.debug(
                f"Added message {message.id} to conversation {conversation_id}"
            )
            return str(message.id)

    def _extract_text_from_message(self, content: ModelMessage) -> Optional[str]:
        """Extract text content from a ModelMessage."""
        try:
            content_attr = getattr(content, "content", None)
            if content_attr and isinstance(content_attr, str):
                return content_attr
            elif hasattr(content, "parts"):
                text_parts = []
                for part in content.parts:
                    if isinstance(part, (TextPart, UserPromptPart)):
                        part_content = getattr(part, "content", None)
                        part_text = getattr(part, "text", None)
                        if part_content:
                            text_parts.append(str(part_content))
                        elif part_text:
                            text_parts.append(str(part_text))
                if text_parts:
                    return " ".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting text from message: {e}")
        return None

    async def _generate_and_store_embedding(
        self, session: AsyncSession, message_id: str, text: str, conversation_id: str
    ):
        """Generate and store embedding for message text."""
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small", input=text
            )
            embedding_vector = response.data[0].embedding

            embedding = MessageEmbedding(
                conversation_id=conversation_id,
                content=text,
                embedding=embedding_vector,
            )
            session.add(embedding)
            logger.debug(f"Generated embedding for message {message_id}")

        except Exception as e:
            logger.error(f"Failed to generate embedding for message {message_id}: {e}")

    async def get_conversation_history(
        self, user_id: str, channel_id: str, limit: int = 50
    ) -> List[ModelMessage]:
        """Get conversation history as ModelMessage objects."""
        session_id = f"{user_id}:{channel_id}"

        async with self.async_session() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.session_id == session_id)
                .options(selectinload(Conversation.messages))
            )
            conversation = result.scalar_one_or_none()

            if conversation is None:
                return []

            messages = sorted(
                conversation.messages, key=lambda m: getattr(m, "created_at")
            )[-limit:]

            # Convert back to ModelMessage objects, filtering out problematic messages
            model_messages = []
            for msg in messages:
                try:
                    # Deserialize JSON back to ModelMessage
                    model_message = ModelMessagesTypeAdapter.validate_python(
                        [msg.content]
                    )[0]

                    # Filter out tool call/response messages that can cause API errors
                    # Only include user prompts and assistant text responses
                    if hasattr(model_message, "parts"):
                        # Check if this message contains tool calls or responses
                        has_tool_content = False
                        for part in model_message.parts:
                            if hasattr(part, "part_kind") and part.part_kind in [
                                "tool-call",
                                "tool-return",
                            ]:
                                has_tool_content = True
                                break

                        # Skip messages with tool content to avoid API errors
                        if has_tool_content:
                            logger.debug(
                                f"Skipping tool message from history: {msg.id}"
                            )
                            continue

                    model_messages.append(model_message)
                except Exception as e:
                    logger.error(f"Failed to deserialize message {msg.id}: {e}")

            return model_messages

    async def search_similar_messages(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[MessageEmbeddingInfo]:
        """Search for similar messages using pgvector embedding similarity."""
        try:
            # Generate embedding for query
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small", input=query_text
            )
            query_embedding = response.data[0].embedding

            # Convert similarity threshold to distance threshold
            # similarity = 1 - distance, so distance = 1 - similarity
            distance_threshold = 1.0 - similarity_threshold

            async with self.async_session() as session:
                # Build query using pgvector's cosine distance operator
                query = select(MessageEmbedding).order_by(
                    MessageEmbedding.embedding.cosine_distance(query_embedding)
                )

                # Filter by distance threshold
                query = query.where(
                    MessageEmbedding.embedding.cosine_distance(query_embedding)
                    <= distance_threshold
                )

                if user_id:
                    # Join with Conversation and User tables for user filtering
                    query = (
                        query.join(
                            Conversation,
                            MessageEmbedding.conversation_id == Conversation.id,
                        )
                        .join(User, Conversation.user_id == User.id)
                        .where(User.user_id == user_id)
                    )

                # Limit results
                query = query.limit(limit)

                result = await session.execute(query)
                embeddings = result.scalars().all()

                # Convert to MessageEmbeddingInfo objects
                similar_messages = [
                    MessageEmbeddingInfo(
                        content=embedding.content,
                        embedding=list(
                            embedding.embedding
                        ),  # Convert Vector to List[float]
                        created_at=embedding.created_at,
                    )
                    for embedding in embeddings
                ]

                return similar_messages

        except Exception as e:
            logger.error(f"Failed to search similar messages: {e}")
            return []

    async def update_user_profile(self, user_id: str, updates: dict):
        """Update user profile information."""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if user:
                # Update fields that exist in the User model
                if "conversation_style" in updates:
                    user.conversation_style = updates["conversation_style"]

                if "topics_of_interest" in updates:
                    user.topics_of_interest = updates["topics_of_interest"]

                setattr(user, "updated_at", datetime.now(timezone.utc))
                await session.commit()
                logger.info(f"Updated profile for user {user_id}")

    async def get_recent_conversations(
        self, user_id: str, days: int = 7, limit: int = 10
    ) -> List[dict]:
        """Get recent conversations for a user."""
        async with self.async_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            result = await session.execute(
                select(Conversation)
                .join(User, Conversation.user_id == User.id)
                .where(
                    and_(
                        User.user_id == user_id, Conversation.created_at >= cutoff_date
                    )
                )
                .order_by(Conversation.created_at.desc())
                .limit(limit)
                .options(selectinload(Conversation.messages))
            )
            conversations = result.scalars().all()

            return [
                {
                    "id": str(conv.id),
                    "session_id": conv.session_id,
                    "channel_id": conv.channel_id,
                    "created_at": conv.created_at.isoformat(),
                    "message_count": len(conv.messages),
                    "last_message": (
                        max(
                            (getattr(msg, "created_at") for msg in conv.messages),
                            default=getattr(conv, "created_at"),
                        ).isoformat()
                        if conv.messages
                        else conv.created_at.isoformat()
                    ),
                }
                for conv in conversations
            ]

    async def can_generate_image(
        self, tool_name: str, user_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """Check if image generation is allowed based on rate limits.

        Args:
            tool_name: Name of the tool requesting generation
            user_id: Optional user ID for user-specific tracking

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        try:
            # Get limits from config
            DAILY_LIMIT = self.config.image_daily_limit
            HOURLY_LIMIT = self.config.image_hourly_limit
            async with self.async_session() as session:
                now = datetime.now(timezone.utc)

                # Check hourly limit
                hour_ago = now - timedelta(hours=1)
                hourly_result = await session.execute(
                    select(ImageUsage).where(ImageUsage.created_at >= hour_ago)
                )
                hourly_count = len(hourly_result.scalars().all())

                # Check daily limit
                day_ago = now - timedelta(days=1)
                daily_result = await session.execute(
                    select(ImageUsage).where(ImageUsage.created_at >= day_ago)
                )
                daily_count = len(daily_result.scalars().all())

                if daily_count >= DAILY_LIMIT:
                    return (
                        False,
                        f"Daily limit reached ({daily_count}/{DAILY_LIMIT}). Try again tomorrow.",
                    )

                if hourly_count >= HOURLY_LIMIT:
                    return (
                        False,
                        f"Hourly limit reached ({hourly_count}/{HOURLY_LIMIT}). Try again later.",
                    )

                logger.info(
                    f"Image generation allowed for {tool_name}. Usage: {hourly_count}/{HOURLY_LIMIT} hourly, {daily_count}/{DAILY_LIMIT} daily"
                )
                return (
                    True,
                    f"Allowed. Current usage: {hourly_count}/{HOURLY_LIMIT} hourly, {daily_count}/{DAILY_LIMIT} daily",
                )

        except Exception as e:
            logger.error(f"Error checking image generation limits: {e}")
            return False, "Error checking rate limits. Please try again."

    async def record_image_generation(
        self, tool_name: str, user_id: Optional[str] = None
    ) -> None:
        """Record that an image was generated.

        Args:
            tool_name: Name of the tool that generated the image
            user_id: Optional user ID for tracking
        """
        try:
            async with self.async_session() as session:
                usage = ImageUsage(tool_name=tool_name, user_id=user_id)
                session.add(usage)
                await session.commit()
                logger.info(f"Recorded image generation for {tool_name}")

        except Exception as e:
            logger.error(f"Error recording image generation: {e}")

    async def close(self):
        """Close the database connection."""
        await self.engine.dispose()
        logger.info("Database connections closed")


# Global instance - using generic name for future flexibility
memory_manager = MemoryManager()
