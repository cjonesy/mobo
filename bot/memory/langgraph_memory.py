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

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.checkpointer = None
        self.store = None
        self._checkpointer_manager = None
        self._store_manager = None
        self._initialized = False
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

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
                        created_at=datetime.now(UTC),
                    )
                    session.add(bot_conv)

                session.commit()
                logger.debug(
                    f"Saved conversation for user {user_id} in channel {channel_id}"
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
