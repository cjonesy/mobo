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
                    aliases TEXT[] DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """
                )
            )
            # Add aliases column if it doesn't exist (migration)
            await conn.execute(
                text(
                    """
                ALTER TABLE user_profiles
                ADD COLUMN IF NOT EXISTS aliases TEXT[] DEFAULT '{}'
            """
                )
            )
            # Remove unused custom_tags column if it exists (cleanup migration)
            await conn.execute(
                text(
                    """
                ALTER TABLE user_profiles
                DROP COLUMN IF EXISTS custom_tags
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
                        SELECT user_id, tone, likes, dislikes, aliases, created_at, updated_at
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
                        "aliases": [],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }

                return {
                    "user_id": row.user_id,
                    "tone": row.tone,
                    "likes": list(row.likes) if row.likes else [],
                    "dislikes": list(row.dislikes) if row.dislikes else [],
                    "aliases": list(row.aliases) if row.aliases else [],
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
                "aliases": [],
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
                        INSERT INTO user_profiles (user_id, tone, likes, dislikes, aliases)
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

    async def add_user_aliases(self, user_id: str, aliases: list[str]) -> None:
        """Add aliases to user's aliases list."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET aliases = array(SELECT DISTINCT unnest(aliases || :aliases)),
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "aliases": aliases},
                )
                await session.commit()
                logger.debug(f"Added aliases for user {user_id}: {aliases}")

        except Exception as e:
            logger.error(f"Failed to add aliases for user {user_id}: {e}")

    async def remove_user_aliases(self, user_id: str, aliases: list[str]) -> None:
        """Remove aliases from user's aliases list."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET aliases = array(SELECT unnest(aliases) EXCEPT SELECT unnest(:aliases)),
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "aliases": aliases},
                )
                await session.commit()
                logger.debug(f"Removed aliases for user {user_id}: {aliases}")

        except Exception as e:
            logger.error(f"Failed to remove aliases for user {user_id}: {e}")

    async def set_user_aliases(self, user_id: str, aliases: list[str]) -> None:
        """Set user's aliases list, replacing any existing aliases."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE user_profiles
                        SET aliases = :aliases,
                            updated_at = now()
                        WHERE user_id = :user_id
                    """
                    ),
                    {"user_id": user_id, "aliases": aliases},
                )
                await session.commit()
                logger.debug(f"Set aliases for user {user_id}: {aliases}")

        except Exception as e:
            logger.error(f"Failed to set aliases for user {user_id}: {e}")

    async def get_user_by_alias(self, alias: str) -> str | None:
        """Get user ID by alias. Returns None if alias not found."""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT user_id FROM user_profiles
                        WHERE :alias = ANY(aliases)
                    """
                    ),
                    {"alias": alias},
                )
                row = result.fetchone()
                return row.user_id if row else None

        except Exception as e:
            logger.error(f"Failed to get user by alias {alias}: {e}")
            return None

    def format_profile_summary(self, profile: dict[str, Any]) -> str:
        """Format user profile into a readable summary string."""
        tone = profile.get("tone", "neutral")
        likes = profile.get("likes", [])
        dislikes = profile.get("dislikes", [])
        aliases = profile.get("aliases", [])

        return f"Tone: {tone}, Likes: {likes}, Dislikes: {dislikes}, Aliases: {aliases}"

    def format_profile_for_prompt(self, profile: dict[str, Any]) -> str:
        """Format user profile for system prompt display."""
        likes = profile.get("likes", [])
        dislikes = profile.get("dislikes", [])
        aliases = profile.get("aliases", [])

        parts = []
        if likes:
            parts.append(f"- They enjoy: {', '.join(likes)}")
        else:
            parts.append("- They enjoy: ")

        if dislikes:
            parts.append(f"- They dislike: {', '.join(dislikes)}")
        else:
            parts.append("- They dislike: ")

        if aliases:
            parts.append(f"- Known aliases/preferred names: {', '.join(aliases)}")
        else:
            parts.append("- Known aliases/preferred names: ")

        return "\n                  ".join(parts)

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
