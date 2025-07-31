"""User profile tracking and management system."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)

from ..config import Config, get_config

logger = logging.getLogger(__name__)


class UserProfileManager:
    """Manages user profiles for personalized bot interactions."""

    def __init__(self) -> None:
        self.config: Config = get_config()
        self.engine: AsyncEngine = create_async_engine(
            self.config.database_url,
            echo=self.config.database_echo,
            pool_size=self.config.database_pool_size,
            max_overflow=self.config.database_max_overflow,
        )
        self.async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize_database(self) -> None:
        """Initialize the user profiles database table."""
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT UNIQUE NOT NULL,
                    tone TEXT DEFAULT 'casual',
                    likes TEXT[] DEFAULT '{}',
                    dislikes TEXT[] DEFAULT '{}',
                    custom_tags JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """
                )
            )

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Get user profile by user ID."""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT user_id, tone, likes, dislikes, custom_tags, created_at, updated_at
                        FROM user_profiles
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id},
                )
                row = result.fetchone()

                if not row:
                    logger.debug(
                        f"No profile found for user {user_id}, creating new one"
                    )
                    await self.create_user_profile(user_id)
                    # Return default profile
                    return {
                        "user_id": user_id,
                        "tone": "casual",
                        "likes": [],
                        "dislikes": [],
                        "custom_tags": {},
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }

                return {
                    "user_id": row.user_id,
                    "tone": row.tone,
                    "likes": list(row.likes) if row.likes else [],
                    "dislikes": list(row.dislikes) if row.dislikes else [],
                    "custom_tags": dict(row.custom_tags) if row.custom_tags else {},
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }

        except Exception as e:
            logger.error(f"Failed to get user profile for {user_id}: {e}")
            # Return default profile on error
            return {
                "user_id": user_id,
                "tone": "casual",
                "likes": [],
                "dislikes": [],
                "custom_tags": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

    async def create_user_profile(self, user_id: str) -> None:
        """Create a new user profile with default values."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO user_profiles (user_id, tone, likes, dislikes, custom_tags)
                        VALUES (:user_id, 'casual', '{}', '{}', '{}')
                        ON CONFLICT (user_id) DO NOTHING
                    """
                    ),
                    {"user_id": user_id},
                )
                await session.commit()
                logger.debug(f"Created user profile for {user_id}")

        except Exception as e:
            logger.error(f"Failed to create user profile for {user_id}: {e}")

    async def update_user_tone(self, user_id: str, tone: str) -> None:
        """Update user's preferred tone."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET tone = :tone, updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "tone": tone},
                )
                await session.commit()
                logger.debug(f"Updated tone for user {user_id} to {tone}")

        except Exception as e:
            logger.error(f"Failed to update tone for user {user_id}: {e}")

    async def add_user_likes(self, user_id: str, likes: list[str]) -> None:
        """Add items to user's likes list."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET likes = array(SELECT DISTINCT unnest(likes || :likes)),
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "likes": likes},
                )
                await session.commit()
                logger.debug(f"Added likes for user {user_id}: {likes}")

        except Exception as e:
            logger.error(f"Failed to add likes for user {user_id}: {e}")

    async def add_user_dislikes(self, user_id: str, dislikes: list[str]) -> None:
        """Add items to user's dislikes list."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET dislikes = array(SELECT DISTINCT unnest(dislikes || :dislikes)),
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "dislikes": dislikes},
                )
                await session.commit()
                logger.debug(f"Added dislikes for user {user_id}: {dislikes}")

        except Exception as e:
            logger.error(f"Failed to add dislikes for user {user_id}: {e}")

    async def remove_user_likes(self, user_id: str, likes: list[str]) -> None:
        """Remove items from user's likes list."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET likes = array(SELECT unnest(likes) EXCEPT SELECT unnest(:likes)),
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "likes": likes},
                )
                await session.commit()
                logger.debug(f"Removed likes for user {user_id}: {likes}")

        except Exception as e:
            logger.error(f"Failed to remove likes for user {user_id}: {e}")

    async def remove_user_dislikes(self, user_id: str, dislikes: list[str]) -> None:
        """Remove items from user's dislikes list."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET dislikes = array(SELECT unnest(dislikes) EXCEPT SELECT unnest(:dislikes)),
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "dislikes": dislikes},
                )
                await session.commit()
                logger.debug(f"Removed dislikes for user {user_id}: {dislikes}")

        except Exception as e:
            logger.error(f"Failed to remove dislikes for user {user_id}: {e}")

    async def update_custom_tags(self, user_id: str, tags: dict[str, Any]) -> None:
        """Update user's custom tags (merge with existing)."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET custom_tags = custom_tags || :tags,
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "tags": tags},
                )
                await session.commit()
                logger.debug(f"Updated custom tags for user {user_id}: {tags}")

        except Exception as e:
            logger.error(f"Failed to update custom tags for user {user_id}: {e}")

    async def get_all_users_with_tone(self, tone: str) -> list[str]:
        """Get all user IDs with a specific tone preference."""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text("SELECT user_id FROM user_profiles WHERE tone = :tone"),
                    {"tone": tone},
                )
                rows = result.fetchall()
                return [row.user_id for row in rows]

        except Exception as e:
            logger.error(f"Failed to get users with tone {tone}: {e}")
            return []

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
