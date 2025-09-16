"""
Test configuration and fixtures for the mobo bot test suite.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from mobo.models import User
from mobo.config import Settings
from mobo.db import Base


# Custom pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running",
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Create test settings with safe defaults."""
    with patch.dict(
        os.environ,
        {
            "DISCORD__TOKEN": "test_token",
            "OPENAI_API_KEY": "test_openai_key",
            "POSTGRES_URL": "sqlite:///:memory:",
            "POSTGRES_ASYNC_URL": "sqlite+aiosqlite:///:memory:",
            "PERSONALITY_PROMPT": "You are a helpful test bot.",
        },
    ):
        return Settings()


@pytest.fixture
async def test_db_engine():
    """Create a PostgreSQL test database engine."""

    # Get PostgreSQL test database URL
    test_postgres_url = os.getenv(
        "TEST_POSTGRES_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/mobo_test",
    )

    try:
        # Create PostgreSQL engine
        engine = create_async_engine(
            test_postgres_url,
            echo=False,
            future=True,
        )

        # Create all tables including vector extensions
        async with engine.begin() as conn:
            # Ensure pgvector extension exists (will not error if already exists)
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        # Cleanup
        await engine.dispose()

    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")
        # This will never be reached, but satisfies the type checker
        yield None


@pytest.fixture
async def test_db_session(test_db_engine):
    """Create a test database session."""
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


# @pytest.fixture
# async def conversation_memory(test_settings):
#     """Create a LangGraphMemory instance for testing."""
#     memory = LangGraphMemory(test_settings.database_url)
#     await memory.initialize()
#     return memory


# @pytest.fixture
# async def user_profiles(test_settings):
#     """User profiles are now handled by LangGraphMemory."""
#     pass


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    return {
        "discord_user_id": "123456789",
        "response_tone": "friendly",
        "likes": [],
        "dislikes": [],
    }


@pytest.fixture
def mock_conversation():
    """Create a mock conversation for testing."""
    return {
        "user_id": "123456789",
        "channel_id": "987654321",
        "guild_id": "555666777",
        "role": "user",
        "content": "Hello, test message!",
        "message_length": 19,
    }


@pytest.fixture
def sample_bot_state():
    """Create a sample bot state for workflow testing."""
    return {
        "user_message": "Hello bot!",
        "user_id": "123456789",
        "channel_id": "987654321",
        "guild_id": "555666777",
        "timestamp": "2024-01-01T00:00:00Z",
        "personality": "You are a helpful Discord bot.",
        "user_context": {
            "discord_user_id": "123456789",
            "response_tone": "friendly",
            "likes": ["coding", "music"],
            "dislikes": ["spam"],
        },
        "messages": [],
        "tool_results": {},
        "tool_errors": {},
        "generated_files": [],
        "final_response": "",
        "model_calls": 0,
    }


# Phase 3: Simple mock tool function (no complex base classes)
def create_mock_tool():
    """Create a simple mock tool function for testing."""
    from langchain_core.tools import tool

    @tool
    async def mock_tool(test_param: str = "default") -> str:
        """A mock tool for testing.

        Args:
            test_param: Test parameter
        """
        return f"Mock result: {test_param}"

    return mock_tool


@pytest.fixture
def mock_tool():
    """Create a mock tool for testing."""
    return create_mock_tool()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock()

    # Mock embeddings
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [MagicMock()]
    mock_embedding_response.data[0].embedding = [
        0.1
    ] * 1536  # Standard OpenAI embedding size
    client.embeddings.create.return_value = mock_embedding_response

    # Mock chat completions
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [MagicMock()]
    mock_chat_response.choices[0].message.content = "Mock AI response"
    client.chat.completions.create.return_value = mock_chat_response

    return client


@pytest.fixture
def mock_discord_message():
    """Mock Discord message for testing."""
    message = MagicMock()
    message.content = "Test message"
    message.author.id = "123456789"
    message.author.display_name = "TestUser"
    message.channel.id = "987654321"
    message.guild.id = "555666777" if hasattr(message, "guild") else None
    return message


# Async test utilities
@pytest.mark.asyncio
async def async_test_wrapper(coro):
    """Wrapper for async test functions."""
    return await coro


# Test data helpers
def create_test_user_data(**overrides):
    """Create test user data with optional overrides."""
    base_data = {
        "discord_user_id": "123456789",
        "response_tone": "friendly",
        "likes": [],
        "dislikes": [],
    }
    base_data.update(overrides)
    return base_data


def create_test_conversation_data(**overrides):
    """Create test conversation data with optional overrides."""
    base_data = {
        "user_id": "123456789",
        "channel_id": "987654321",
        "guild_id": "555666777",
        "role": "user",
        "content": "Test message",
        "message_length": 12,
    }
    base_data.update(overrides)
    return base_data
