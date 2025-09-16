"""
Tests for memory models and database functionality.
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock

from mobo.models import (
    User,
    UserLike,
    UserDislike,
    UserAlias,
    BotInteraction,
)


class TestMemoryModels:
    """Test the SQLAlchemy memory models."""

    @pytest.fixture
    def mock_user(self):
        """Mock user data for testing."""
        return {
            "discord_user_id": "123456789012345678",
            "response_tone": "friendly",
        }

    @pytest.fixture
    def mock_bot_interaction(self):
        """Mock bot interaction data for testing."""
        return {
            "bot_user_id": "987654321098765432",
            "channel_id": "channel_123456789",
            "guild_id": "guild_123456789",
            "bot_name": "TestBot",
            "interaction_type": "message",
            "interaction_count": 1,
            "is_currently_active": True,
        }

    @pytest.mark.asyncio
    async def test_user_creation(self, test_db_session, mock_user):
        """Test creating a user in the database."""
        user = User(**mock_user)
        test_db_session.add(user)
        await test_db_session.commit()

        # Verify the user was created
        result = await test_db_session.get(User, mock_user["discord_user_id"])
        assert result is not None
        assert result.discord_user_id == mock_user["discord_user_id"]
        assert result.response_tone == mock_user["response_tone"]

    @pytest.mark.asyncio
    async def test_user_likes_dislikes(self, test_db_session):
        """Test user likes and dislikes relationships."""
        user = User(discord_user_id="123456789012345678", response_tone="neutral")
        test_db_session.add(user)

        # Add likes and dislikes
        like = UserLike(user=user, term="programming", confidence=0.9)
        dislike = UserDislike(user=user, term="spam", confidence=0.8)

        test_db_session.add_all([like, dislike])
        await test_db_session.commit()

        # Verify relationships
        result = await test_db_session.get(User, "123456789012345678")
        assert len(result.likes) == 1
        assert len(result.dislikes) == 1
        assert result.likes[0].term == "programming"
        assert result.dislikes[0].term == "spam"

    @pytest.mark.asyncio
    async def test_bot_interaction_creation(
        self, test_db_session, mock_bot_interaction
    ):
        """Test creating a bot interaction in the database."""
        interaction = BotInteraction(**mock_bot_interaction)
        test_db_session.add(interaction)
        await test_db_session.commit()

        # Verify the interaction was created
        assert interaction.id is not None
        assert interaction.bot_user_id == mock_bot_interaction["bot_user_id"]
        assert interaction.interaction_count == 1
