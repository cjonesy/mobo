"""
Tests for memory models and database functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from bot.memory.models import (
    User,
    Conversation,
    UserLike,
    UserDislike,
    UserAlias,
    ConversationSummary,
    BotInteraction,
    validate_conversation_data,
    validate_user_data,
    get_user_by_discord_id,
    get_recent_conversations,
)
# Legacy memory tests - now using LangGraph built-in patterns
# from bot.memory.langgraph_memory import LangGraphMemory


class TestMemoryModels:
    """Test the SQLAlchemy memory models."""

    @pytest.mark.asyncio
    async def test_user_creation(self, test_db_session, mock_user):
        """Test creating a user in the database."""
        user = User(**mock_user)
        test_db_session.add(user)
        await test_db_session.commit()

        # Retrieve and verify
        retrieved_user = await test_db_session.get(User, mock_user["discord_user_id"])
        assert retrieved_user is not None
        assert retrieved_user.display_name == mock_user["display_name"]
        assert retrieved_user.response_tone == mock_user["response_tone"]

    @pytest.mark.asyncio
    async def test_conversation_creation(self, test_db_session, mock_conversation):
        """Test creating a conversation in the database."""
        conversation = Conversation(**mock_conversation)
        test_db_session.add(conversation)
        await test_db_session.commit()

        # Verify the conversation was created
        assert conversation.id is not None
        assert conversation.content == mock_conversation["content"]
        assert conversation.role == mock_conversation["role"]
        assert conversation.user_id == mock_conversation["user_id"]

    @pytest.mark.asyncio
    async def test_user_likes_relationship(self, test_db_session, mock_user):
        """Test the user likes relationship."""
        # Create user
        user = User(**mock_user)
        test_db_session.add(user)
        await test_db_session.commit()

        # Add likes
        like1 = UserLike(
            user_id=user.discord_user_id, like_term="coding", confidence=0.9
        )
        like2 = UserLike(
            user_id=user.discord_user_id, like_term="music", confidence=0.8
        )

        test_db_session.add_all([like1, like2])
        await test_db_session.commit()

        # Refresh user to load relationships
        await test_db_session.refresh(user)

        # Verify relationships
        assert len(user.likes) == 2
        like_terms = [like.like_term for like in user.likes]
        assert "coding" in like_terms
        assert "music" in like_terms

    @pytest.mark.asyncio
    async def test_user_dislikes_relationship(self, test_db_session, mock_user):
        """Test the user dislikes relationship."""
        # Create user
        user = User(**mock_user)
        test_db_session.add(user)
        await test_db_session.commit()

        # Add dislike
        dislike = UserDislike(
            user_id=user.discord_user_id, dislike_term="spam", confidence=1.0
        )
        test_db_session.add(dislike)
        await test_db_session.commit()

        # Refresh and verify
        await test_db_session.refresh(user)
        assert len(user.dislikes) == 1
        assert user.dislikes[0].dislike_term == "spam"

    def test_validate_conversation_data_valid(self):
        """Test conversation data validation with valid data."""
        valid_data = {
            "user_id": "123456789",
            "channel_id": "987654321",
            "role": "user",
            "content": "Test message",
        }

        is_valid, error = validate_conversation_data(valid_data)
        assert is_valid
        assert error == ""

    def test_validate_conversation_data_invalid_role(self):
        """Test conversation data validation with invalid role."""
        invalid_data = {
            "user_id": "123456789",
            "channel_id": "987654321",
            "role": "invalid_role",
            "content": "Test message",
        }

        is_valid, error = validate_conversation_data(invalid_data)
        assert not is_valid
        assert "Invalid role" in error

    def test_validate_conversation_data_missing_field(self):
        """Test conversation data validation with missing field."""
        invalid_data = {
            "user_id": "123456789",
            "channel_id": "987654321",
            # Missing role and content
        }

        is_valid, error = validate_conversation_data(invalid_data)
        assert not is_valid
        assert "Missing required field" in error

    def test_validate_user_data_valid(self):
        """Test user data validation with valid data."""
        valid_data = {"discord_user_id": "123456789", "display_name": "TestUser"}

        is_valid, error = validate_user_data(valid_data)
        assert is_valid
        assert error == ""

    def test_validate_user_data_invalid_user_id(self):
        """Test user data validation with invalid user ID."""
        invalid_data = {"discord_user_id": "not_a_number", "display_name": "TestUser"}

        is_valid, error = validate_user_data(invalid_data)
        assert not is_valid
        assert "Invalid Discord user ID format" in error


class TestConversationAnalytics:
    """Test conversation analytics and insights."""

    @pytest.mark.asyncio
    async def test_bot_interaction_tracking(self, test_db_session):
        """Test bot interaction tracking."""
        from bot.memory.models import BotInteraction

        interaction = BotInteraction(
            bot_user_id="bot_123",
            channel_id="channel_456",
            guild_id="guild_789",
            interaction_count=5,
            bot_name="TestBot",
        )

        test_db_session.add(interaction)
        await test_db_session.commit()

        assert interaction.id is not None
        assert interaction.bot_name == "TestBot"
        assert interaction.interaction_count == 5

    @pytest.mark.asyncio
    async def test_conversation_summary(self, test_db_session):
        """Test conversation summary storage."""
        from bot.memory.models import ConversationSummary

        summary = ConversationSummary(
            channel_id="channel_123",
            guild_id="guild_456",
            start_time=datetime.utcnow() - timedelta(hours=2),
            end_time=datetime.utcnow(),
            summary="Users discussed programming topics",
            message_count=15,
        )

        test_db_session.add(summary)
        await test_db_session.commit()

        assert summary.id is not None
        assert summary.message_count == 15
        assert "programming" in summary.summary
