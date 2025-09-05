"""
Modern LangGraph memory using full PostgreSQL persistence.

This replaces all custom memory logic with LangGraph's native PostgreSQL storage:
- AsyncPostgresSaver for conversation state checkpointing (full PostgreSQL persistence)
- PostgresStore for cross-thread user memory (PostgreSQL persistence)

Uses AsyncPostgresSaver from langgraph.checkpoint.postgres.aio for proper async support.
The regular PostgresSaver has a bug where aget_tuple() raises NotImplementedError.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, UTC

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openai import AsyncOpenAI

from .models import Conversation, get_recent_conversations

logger = logging.getLogger(__name__)


class LangGraphMemory:
    """
    Modern LangGraph memory using PostgreSQL persistence.

    Uses:
    - PostgresSaver for conversation state checkpointing
    - PostgresStore for cross-thread user memory
    - Thread-based conversation management with proper context manager handling
    """

    def __init__(self, database_url: str, openai_api_key: str):
        self.database_url = database_url
        self.checkpointer = None
        self.store = None
        self._checkpointer_manager = None
        self._store_manager = None
        self._initialized = False
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # OpenAI client for embeddings
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)

        logger.info("🚀 Memory initialized with PostgreSQL LangGraph patterns")

    async def initialize(self):
        """Initialize the LangGraph PostgreSQL backends with proper context manager handling."""
        if self._initialized:
            return

        try:
            # Initialize AsyncPostgresSaver context manager for async operations
            self._checkpointer_manager = AsyncPostgresSaver.from_conn_string(
                self.database_url
            )
            self.checkpointer = await self._checkpointer_manager.__aenter__()
            await self.checkpointer.setup()
            logger.info("✅ AsyncPostgresSaver initialized and setup complete")

            # Initialize PostgresStore context manager
            self._store_manager = PostgresStore.from_conn_string(self.database_url)
            self.store = self._store_manager.__enter__()
            self.store.setup()
            logger.info("✅ PostgresStore initialized and setup complete")

            self._initialized = True
            logger.info("✅ LangGraph PostgreSQL storage ready")

        except Exception as e:
            logger.error(f"❌ Error initializing LangGraph PostgreSQL memory: {e}")
            # Clean up on error
            await self._cleanup_managers()
            raise

    def get_thread_id(self, channel_id: str) -> str:
        """Get thread ID for Discord channel-based conversations."""
        return f"discord_channel_{channel_id}"

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get user profile using LangGraph store (cross-thread memory).

        Args:
            user_id: Discord user ID

        Returns:
            User profile dictionary
        """
        try:
            # Use LangGraph store to get cross-thread user data
            items = await self.store.aget(namespace="user_profiles", key=user_id)

            if items:
                # Handle both list of items and single item responses
                if isinstance(items, list) and len(items) > 0:
                    return items[0].value
                elif hasattr(items, "value"):
                    return items.value
            else:
                # Create default profile
                default_profile = {
                    "discord_user_id": user_id,
                    "display_name": f"User_{user_id[:8]}",
                    "response_tone": "neutral",
                    "likes": [],
                    "dislikes": [],
                    "created_at": None,  # Will be set by store
                }

                # Store default profile
                await self.store.aput(
                    namespace="user_profiles", key=user_id, value=default_profile
                )

                return default_profile

        except Exception as e:
            logger.error(f"Error getting user profile for {user_id}: {e}")
            # Return minimal default
            return {
                "discord_user_id": user_id,
                "display_name": f"User_{user_id[:8]}",
                "response_tone": "neutral",
                "likes": [],
                "dislikes": [],
            }

    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]):
        """
        Update user profile using LangGraph store.

        Args:
            user_id: Discord user ID
            updates: Profile updates to apply
        """
        try:
            # Get current profile
            current_profile = await self.get_user_profile(user_id)

            # Apply updates
            current_profile.update(updates)

            # Store updated profile
            await self.store.aput(
                namespace="user_profiles", key=user_id, value=current_profile
            )

            logger.debug(f"Updated profile for {user_id}: {updates}")

        except Exception as e:
            logger.error(f"Error updating user profile for {user_id}: {e}")

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI's embedding model.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding
        """
        if not self.openai_client:
            logger.warning(
                "OpenAI client not configured - skipping embedding generation"
            )
            return None

        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small", input=text, encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    async def save_conversation(
        self,
        user_id: str,
        channel_id: str,
        guild_id: str = None,
        user_message: str = None,
        bot_response: str = None,
    ):
        """
        Save conversation messages to the database.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID (optional for DMs)
            user_message: User's message content
            bot_response: Bot's response content
        """
        try:
            # Generate embeddings for the messages
            user_embedding = None
            bot_embedding = None

            if user_message:
                user_embedding = await self._generate_embedding(user_message)
            if bot_response:
                bot_embedding = await self._generate_embedding(bot_response)

            with self.SessionLocal() as session:
                # Save user message if provided
                if user_message:
                    user_conv = Conversation(
                        user_id=user_id,
                        channel_id=channel_id,
                        guild_id=guild_id,
                        role="user",
                        content=user_message,
                        message_length=len(user_message),
                        embedding=user_embedding,
                        created_at=datetime.now(UTC),
                    )
                    session.add(user_conv)

                # Save bot response if provided
                if bot_response:
                    bot_conv = Conversation(
                        user_id=user_id,
                        channel_id=channel_id,
                        guild_id=guild_id,
                        role="assistant",
                        content=bot_response,
                        message_length=len(bot_response),
                        embedding=bot_embedding,
                        created_at=datetime.now(UTC),
                    )
                    session.add(bot_conv)

                session.commit()
                logger.debug(
                    f"Saved conversation with embeddings for user {user_id} in channel {channel_id}"
                )

        except Exception as e:
            logger.error(f"Error saving conversation: {e}")

    async def get_conversation_history(
        self, channel_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation history for a channel.

        Args:
            channel_id: Discord channel ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of conversation messages as dictionaries
        """
        try:
            with self.SessionLocal() as session:
                conversations = get_recent_conversations(session, channel_id, limit)

                # Convert to dictionaries for the bot state
                history = []
                for conv in conversations:
                    history.append(
                        {
                            "role": conv.role,
                            "content": conv.content,
                            "user_id": conv.user_id,
                            "timestamp": conv.created_at.isoformat(),
                            "message_length": conv.message_length,
                        }
                    )

                # Reverse to get chronological order (oldest first)
                history.reverse()

                logger.debug(
                    f"Retrieved {len(history)} conversation messages for channel {channel_id}"
                )
                return history

        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []

    async def search_relevant_conversations(
        self,
        query: str,
        channel_id: str = None,
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search for semantically relevant conversations using vector similarity.

        Args:
            query: The text to search for similar conversations
            channel_id: Optional channel ID to limit search scope
            limit: Maximum number of results to return
            similarity_threshold: Minimum cosine similarity score (0.0-1.0)

        Returns:
            List of relevant conversation messages with similarity scores
        """
        if not self.openai_client:
            logger.warning("OpenAI client not configured - skipping semantic search")
            return []

        try:
            # Generate embedding for the query
            query_embedding = await self._generate_embedding(query)
            if not query_embedding:
                return []

            with self.SessionLocal() as session:
                # Build the query using SQLAlchemy ORM with proper vector operations
                query = (
                    session.query(
                        Conversation.id,
                        Conversation.user_id,
                        Conversation.channel_id,
                        Conversation.guild_id,
                        Conversation.role,
                        Conversation.content,
                        Conversation.message_length,
                        Conversation.created_at,
                        Conversation.embedding.cosine_distance(query_embedding).label(
                            "similarity_distance"
                        ),
                        (
                            1 - Conversation.embedding.cosine_distance(query_embedding)
                        ).label("similarity_score"),
                    )
                    .filter(Conversation.embedding.is_not(None))
                    .filter(
                        (1 - Conversation.embedding.cosine_distance(query_embedding))
                        >= similarity_threshold
                    )
                )

                if channel_id:
                    query = query.filter(Conversation.channel_id == channel_id)

                query = query.order_by(
                    (1 - Conversation.embedding.cosine_distance(query_embedding)).desc()
                ).limit(limit)

                rows = query.all()

            # Convert to dictionaries
            relevant_conversations = []
            for row in rows:
                relevant_conversations.append(
                    {
                        "id": str(row.id),
                        "role": row.role,
                        "content": row.content,
                        "user_id": row.user_id,
                        "channel_id": row.channel_id,
                        "guild_id": row.guild_id,
                        "timestamp": row.created_at.isoformat(),
                        "message_length": row.message_length,
                        "similarity_score": float(row.similarity_score),
                        "similarity_distance": float(row.similarity_distance),
                    }
                )

                logger.debug(
                    f"Found {len(relevant_conversations)} relevant conversations for query: {query[:50]}..."
                )
                return relevant_conversations

        except Exception as e:
            logger.error(f"Error searching relevant conversations: {e}")
            return []

    async def get_hybrid_conversation_context(
        self,
        current_message: str,
        channel_id: str,
        recent_limit: int = 5,
        relevant_limit: int = 3,
        similarity_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Get hybrid conversation context combining recent messages and semantically relevant ones.

        Args:
            current_message: The current user message to find context for
            channel_id: Discord channel ID
            recent_limit: Number of recent messages to include
            relevant_limit: Number of semantically relevant messages to include
            similarity_threshold: Minimum similarity score for relevant messages

        Returns:
            Dictionary with recent_messages, relevant_messages, and formatted context
        """
        try:
            # Get recent messages (chronological)
            recent_messages = await self.get_conversation_history(
                channel_id=channel_id, limit=recent_limit
            )

            # Get semantically relevant messages
            relevant_messages = await self.search_relevant_conversations(
                query=current_message,
                channel_id=channel_id,
                limit=relevant_limit,
                similarity_threshold=similarity_threshold,
            )

            # Remove duplicates (if recent messages are also in relevant messages)
            recent_ids = {msg.get("id") for msg in recent_messages if msg.get("id")}
            relevant_messages = [
                msg for msg in relevant_messages if msg.get("id") not in recent_ids
            ]

            # Build formatted context
            context_parts = []

            if recent_messages:
                context_parts.append("RECENT CONVERSATION:")
                for msg in recent_messages[-3:]:  # Last 3 recent messages
                    role_label = "User" if msg["role"] == "user" else "Bot"
                    context_parts.append(f"{role_label}: {msg['content']}")

            if relevant_messages:
                context_parts.append("\nRELEVANT PAST CONVERSATIONS:")
                for msg in relevant_messages:
                    role_label = "User" if msg["role"] == "user" else "Bot"
                    similarity = msg.get("similarity_score", 0)
                    context_parts.append(
                        f"{role_label} (similarity: {similarity:.2f}): {msg['content']}"
                    )

            formatted_context = (
                "\n".join(context_parts)
                if context_parts
                else "No conversation context available."
            )

            return {
                "recent_messages": recent_messages,
                "relevant_messages": relevant_messages,
                "formatted_context": formatted_context,
                "total_context_messages": len(recent_messages) + len(relevant_messages),
            }

        except Exception as e:
            logger.error(f"Error getting hybrid conversation context: {e}")
            return {
                "recent_messages": [],
                "relevant_messages": [],
                "formatted_context": "No conversation context available.",
                "total_context_messages": 0,
            }

    async def _cleanup_managers(self):
        """Clean up context managers properly (async for AsyncPostgresSaver)."""
        if self._checkpointer_manager and self.checkpointer:
            try:
                await self._checkpointer_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing AsyncPostgresSaver manager: {e}")

        if self._store_manager and self.store:
            try:
                self._store_manager.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing PostgresStore manager: {e}")

        self.checkpointer = None
        self.store = None
        self._checkpointer_manager = None
        self._store_manager = None

    async def close(self):
        """Close PostgreSQL memory resources with proper context manager cleanup."""
        try:
            await self._cleanup_managers()
            self._initialized = False
            logger.info("🔒 LangGraph PostgreSQL memory closed")
        except Exception as e:
            logger.warning(f"Error closing LangGraph PostgreSQL memory: {e}")


def get_config_for_thread(thread_id: str) -> Dict[str, Any]:
    """
    Get LangGraph config for thread-based conversation.

    Args:
        thread_id: Thread identifier

    Returns:
        LangGraph configuration dictionary
    """
    return {"configurable": {"thread_id": thread_id}}
