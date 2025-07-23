"""
Memory system for PydanticAI Discord bot.

This module provides persistent memory storage with semantic search capabilities
using vector embeddings for intelligent conversation management.
"""

import json
import logging
import re
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
        # Regex pattern for Discord mentions: <@user_id> or <@!user_id>
        self.mention_pattern = re.compile(r"<@!?(\d+)>")

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
        """Get existing channel conversation or create new one. Returns conversation ID."""
        async with self.async_session() as session:
            # Ensure user exists (for user profile tracking)
            user_result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if user is None:
                user = User(user_id=user_id, username="")
                session.add(user)
                await session.commit()

            # Look for channel-wide conversation
            conversation_result = await session.execute(
                select(Conversation).where(Conversation.channel_id == channel_id)
            )
            conversation = conversation_result.scalar_one_or_none()

            if conversation is None:
                # Create a channel-wide conversation
                conversation = Conversation(channel_id=channel_id)
                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)
                logger.info(
                    f"Started new channel conversation {conversation.id} in channel {channel_id}"
                )
            else:
                logger.info(
                    f"Using existing channel conversation {conversation.id} in channel {channel_id}"
                )

            return str(conversation.id)

    async def add_message(
        self,
        conversation_id: str,
        content: ModelMessage,
        message_type: str = "user",
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Add a message to the conversation."""
        async with self.async_session() as session:
            # Get username once at storage time for user messages
            username = None
            if message_type == "user" and user_id:
                user_result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = user_result.scalar_one_or_none()
                username = (
                    user.username if user and user.username else f"User{user_id[-4:]}"
                )

                # Format message content cleanly at storage time
                if hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "content"):
                            # Resolve @-mentions in content
                            resolved_content = await self._resolve_mentions(
                                session, part.content
                            )
                            part.content = f"[{username}]: {resolved_content}"
                        elif hasattr(part, "text"):
                            # Resolve @-mentions in text
                            resolved_text = await self._resolve_mentions(
                                session, part.text
                            )
                            part.text = f"[{username}]: {resolved_text}"

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
                user_id=user_id if message_type == "user" else None,
                username=username,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            # Extract text for embeddings (after mention resolution)
            text_content = self._extract_text_from_message(content)
            if text_content:
                # Resolve mentions in the text used for embeddings too
                resolved_text_content = await self._resolve_mentions(
                    session, text_content
                )
                await self._generate_and_store_embedding(
                    session, str(message.id), resolved_text_content, conversation_id
                )

            await session.commit()
            logger.debug(
                f"Added message {message.id} to conversation {conversation_id}"
            )
            return str(message.id)

    async def _resolve_mentions(self, session, text: str) -> str:
        """Resolve Discord @-mentions to readable usernames."""
        if not text or "<@" not in text:
            return text

        async def replace_mention(match):
            mentioned_user_id = match.group(1)

            # Look up the mentioned user in our database
            user_result = await session.execute(
                select(User).where(User.user_id == mentioned_user_id)
            )
            user = user_result.scalar_one_or_none()

            if user and user.username:
                return f"@{user.username}"
            else:
                # If user not in our database, use a generic format
                return f"@User{mentioned_user_id[-4:]}"

        # Replace all mentions in the text
        result = text
        for match in self.mention_pattern.finditer(text):
            mention_replacement = await replace_mention(match)
            result = result.replace(match.group(0), mention_replacement)

        return result

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
        """Get channel-wide conversation history as ModelMessage objects."""
        async with self.async_session() as session:
            # Get the channel-wide conversation (not user-specific)
            result = await session.execute(
                select(Conversation)
                .where(Conversation.channel_id == channel_id)
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
                    # Username formatting already done at storage time
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

    async def get_user_conversation_history(
        self, user_id: str, channel_id: str, limit: int = 50
    ) -> List[ModelMessage]:
        """Get conversation history for a specific user within the channel."""
        async with self.async_session() as session:
            # Get messages from the specific user in this channel
            result = await session.execute(
                select(Message)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(
                    and_(
                        Conversation.channel_id == channel_id,
                        Message.user_id == user_id,
                    )
                )
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = result.scalars().all()

            # Convert to ModelMessage objects (username already formatted at storage time)
            model_messages = []
            for msg in messages:
                try:
                    model_message = ModelMessagesTypeAdapter.validate_python(
                        [msg.content]
                    )[0]
                    model_messages.append(model_message)
                except Exception as e:
                    logger.error(f"Failed to deserialize message {msg.id}: {e}")

            # Return in chronological order
            return list(reversed(model_messages))

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
                    # Get conversations where this user has participated
                    user_conversations_subquery = (
                        select(Message.conversation_id)
                        .where(Message.user_id == user_id)
                        .distinct()
                        .subquery()
                    )

                    # Filter embeddings to only those conversations
                    query = query.where(
                        MessageEmbedding.conversation_id.in_(
                            select(user_conversations_subquery.c.conversation_id)
                        )
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

                if "topics_disliked" in updates:
                    user.topics_disliked = updates["topics_disliked"]

                setattr(user, "updated_at", datetime.now(timezone.utc))
                await session.commit()
                logger.info(f"Updated profile for user {user_id}")

    async def get_recent_conversations(
        self, user_id: str = None, days: int = 7, limit: int = 10
    ) -> List[dict]:
        """Get recent channel conversations. User_id parameter kept for compatibility but not used."""
        async with self.async_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            result = await session.execute(
                select(Conversation)
                .where(Conversation.created_at >= cutoff_date)
                .order_by(Conversation.created_at.desc())
                .limit(limit)
                .options(selectinload(Conversation.messages))
            )
            conversations = result.scalars().all()

            return [
                {
                    "id": str(conv.id),
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
