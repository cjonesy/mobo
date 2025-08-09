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

    async def _get_user_id(
        self, session: AsyncSession, discord_user_id: str
    ) -> int | None:
        """Get internal user ID from discord_user_id. Returns None if user not found."""
        result = await session.execute(
            text("SELECT id FROM users WHERE discord_user_id = :discord_user_id"),
            {"discord_user_id": discord_user_id},
        )
        user = result.fetchone()
        if not user:
            logger.error(f"User {discord_user_id} not found")
            return None
        return user.id

    async def initialize_database(self) -> None:
        """Initialize the database tables."""
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    discord_user_id TEXT UNIQUE NOT NULL,
                    discord_display_name TEXT NOT NULL,
                    tone TEXT DEFAULT 'casual',
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """
                )
            )

            # Create user_aliases table
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS user_aliases (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    alias TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now(),
                    UNIQUE(user_id, alias)
                )
            """
                )
            )

            # Create user_likes table
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS user_likes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    like_term TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now(),
                    UNIQUE(user_id, like_term)
                )
            """
                )
            )

            # Create user_dislikes table
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS user_dislikes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    dislike_term TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now(),
                    UNIQUE(user_id, dislike_term)
                )
            """
                )
            )

    async def get_user_profile(
        self, discord_user_id: str, display_name: str | None = None
    ) -> dict[str, Any]:
        """Get user profile by Discord user ID."""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT
                            u.id,
                            u.discord_user_id,
                            u.discord_display_name,
                            u.tone,
                            u.created_at,
                            u.updated_at,
                            array_agg(DISTINCT a.alias) as aliases,
                            array_agg(DISTINCT l.like_term) as likes,
                            array_agg(DISTINCT d.dislike_term) as dislikes
                        FROM users u
                        LEFT JOIN user_aliases a ON u.id = a.user_id
                        LEFT JOIN user_likes l ON u.id = l.user_id
                        LEFT JOIN user_dislikes d ON u.id = d.user_id
                        WHERE u.discord_user_id = :discord_user_id
                        GROUP BY u.id
                    """
                    ),
                    {"discord_user_id": discord_user_id},
                )
                row = result.fetchone()

                if not row:
                    logger.info(
                        f"No profile found for user {discord_user_id}, creating new one"
                    )
                    if not display_name:
                        display_name = ""
                    await self.create_user_profile(discord_user_id, display_name)
                    # Return default profile
                    return {
                        "discord_user_id": discord_user_id,
                        "discord_display_name": display_name,
                        "tone": "casual",
                        "likes": [],
                        "dislikes": [],
                        "aliases": [],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }

                # Filter out None values from array_agg
                aliases = [a for a in row.aliases if a is not None]
                likes = [l for l in row.likes if l is not None]
                dislikes = [d for d in row.dislikes if d is not None]

                return {
                    "discord_user_id": row.discord_user_id,
                    "discord_display_name": row.discord_display_name,
                    "tone": row.tone,
                    "likes": likes,
                    "dislikes": dislikes,
                    "aliases": aliases,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }

        except Exception as e:
            logger.error(f"Failed to get user profile for {discord_user_id}: {e}")
            # Return default profile on error
            if not display_name:
                display_name = ""
            return {
                "discord_user_id": discord_user_id,
                "discord_display_name": display_name,
                "tone": "casual",
                "likes": [],
                "dislikes": [],
                "aliases": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

    async def create_user_profile(
        self, discord_user_id: str, display_name: str
    ) -> None:
        """Create a new user profile with default values."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO users (discord_user_id, discord_display_name, tone)
                        VALUES (:discord_user_id, :display_name, 'casual')
                        ON CONFLICT (discord_user_id) DO NOTHING
                    """
                    ),
                    {"discord_user_id": discord_user_id, "display_name": display_name},
                )
                await session.commit()
                logger.info(f"Created user profile for {discord_user_id}")

        except Exception as e:
            logger.error(f"Failed to create user profile for {discord_user_id}: {e}")

    async def update_user_tone(self, discord_user_id: str, tone: str) -> None:
        """Update user's preferred tone."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE users
                        SET tone = :tone, updated_at = now()
                        WHERE discord_user_id = :discord_user_id
                    """
                    ),
                    {"discord_user_id": discord_user_id, "tone": tone},
                )
                await session.commit()
                logger.info(f"Updated tone for user {discord_user_id} to {tone}")

        except Exception as e:
            logger.error(f"Failed to update tone for user {discord_user_id}: {e}")

    async def add_user_likes(self, discord_user_id: str, likes: list[str]) -> None:
        """Add items to user's likes list."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Insert new likes
                for like in likes:
                    await session.execute(
                        text(
                            """
                            INSERT INTO user_likes (user_id, like_term)
                            VALUES (:user_id, :like_term)
                            ON CONFLICT (user_id, like_term) DO NOTHING
                        """
                        ),
                        {"user_id": user_id, "like_term": like},
                    )
                await session.commit()
                logger.info(f"Added likes for user {discord_user_id}: {likes}")

        except Exception as e:
            logger.error(f"Failed to add likes for user {discord_user_id}: {e}")

    async def add_user_dislikes(
        self, discord_user_id: str, dislikes: list[str]
    ) -> None:
        """Add items to user's dislikes list."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Insert new dislikes
                for dislike in dislikes:
                    await session.execute(
                        text(
                            """
                            INSERT INTO user_dislikes (user_id, dislike_term)
                            VALUES (:user_id, :dislike_term)
                            ON CONFLICT (user_id, dislike_term) DO NOTHING
                        """
                        ),
                        {"user_id": user_id, "dislike_term": dislike},
                    )
                await session.commit()
                logger.info(f"Added dislikes for user {discord_user_id}: {dislikes}")

        except Exception as e:
            logger.error(f"Failed to add dislikes for user {discord_user_id}: {e}")

    async def remove_user_likes(self, discord_user_id: str, likes: list[str]) -> None:
        """Remove items from user's likes list."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Delete specified likes
                await session.execute(
                    text(
                        """
                        DELETE FROM user_likes
                        WHERE user_id = :user_id AND like_term = ANY(:likes)
                    """
                    ),
                    {"user_id": user_id, "likes": likes},
                )
                await session.commit()
                logger.info(f"Removed likes for user {discord_user_id}: {likes}")

        except Exception as e:
            logger.error(f"Failed to remove likes for user {discord_user_id}: {e}")

    async def remove_user_dislikes(
        self, discord_user_id: str, dislikes: list[str]
    ) -> None:
        """Remove items from user's dislikes list."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Delete specified dislikes
                await session.execute(
                    text(
                        """
                        DELETE FROM user_dislikes
                        WHERE user_id = :user_id AND dislike_term = ANY(:dislikes)
                    """
                    ),
                    {"user_id": user_id, "dislikes": dislikes},
                )
                await session.commit()
                logger.info(f"Removed dislikes for user {discord_user_id}: {dislikes}")

        except Exception as e:
            logger.error(f"Failed to remove dislikes for user {discord_user_id}: {e}")

    async def add_user_aliases(self, discord_user_id: str, aliases: list[str]) -> None:
        """Add aliases to user's aliases list."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Insert new aliases
                for alias in aliases:
                    await session.execute(
                        text(
                            """
                            INSERT INTO user_aliases (user_id, alias)
                            VALUES (:user_id, :alias)
                            ON CONFLICT (user_id, alias) DO NOTHING
                        """
                        ),
                        {"user_id": user_id, "alias": alias},
                    )
                await session.commit()
                logger.info(f"Added aliases for user {discord_user_id}: {aliases}")

        except Exception as e:
            logger.error(f"Failed to add aliases for user {discord_user_id}: {e}")

    async def remove_user_aliases(
        self, discord_user_id: str, aliases: list[str]
    ) -> None:
        """Remove aliases from user's aliases list."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Delete specified aliases
                await session.execute(
                    text(
                        """
                        DELETE FROM user_aliases
                        WHERE user_id = :user_id AND alias = ANY(:aliases)
                    """
                    ),
                    {"user_id": user_id, "aliases": aliases},
                )
                await session.commit()
                logger.info(f"Removed aliases for user {discord_user_id}: {aliases}")

        except Exception as e:
            logger.error(f"Failed to remove aliases for user {discord_user_id}: {e}")

    async def set_user_aliases(self, discord_user_id: str, aliases: list[str]) -> None:
        """Set user's aliases list, replacing any existing aliases."""
        try:
            async with self.async_session() as session:
                user_id = await self._get_user_id(session, discord_user_id)
                if user_id is None:
                    return

                # Delete all existing aliases
                await session.execute(
                    text("DELETE FROM user_aliases WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )

                # Insert new aliases
                for alias in aliases:
                    await session.execute(
                        text(
                            """
                            INSERT INTO user_aliases (user_id, alias)
                            VALUES (:user_id, :alias)
                        """
                        ),
                        {"user_id": user_id, "alias": alias},
                    )
                await session.commit()
                logger.info(f"Set aliases for user {discord_user_id}: {aliases}")

        except Exception as e:
            logger.error(f"Failed to set aliases for user {discord_user_id}: {e}")

    async def get_users_by_like(self, like: str) -> list[tuple[str, str]]:
        """Get Discord users by a like. Returns empty list if none found.

        The search is case-insensitive and matches any substring.
        For example, searching for "cat" would match "cats", "scatter", etc.

        Returns:
            List of tuples containing (discord_user_id, discord_display_name)
        """
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT DISTINCT u.discord_user_id, u.discord_display_name
                        FROM users u
                        JOIN user_likes l ON u.id = l.user_id
                        WHERE l.like_term ILIKE :pattern
                    """
                    ),
                    {"pattern": f"%{like}%"},
                )
                rows = result.fetchall()
                return [(row.discord_user_id, row.discord_display_name) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get users by like {like}: {e}")
            return []

    async def get_users_by_dislike(self, dislike: str) -> list[tuple[str, str]]:
        """Get Discord users by a dislike. Returns empty list if none found.

        The search is case-insensitive and matches any substring.
        For example, searching for "spam" would match "spam", "spammers", etc.

        Returns:
            List of tuples containing (discord_user_id, discord_display_name)
        """
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT DISTINCT u.discord_user_id, u.discord_display_name
                        FROM users u
                        JOIN user_dislikes d ON u.id = d.user_id
                        WHERE d.dislike_term ILIKE :pattern
                    """
                    ),
                    {"pattern": f"%{dislike}%"},
                )
                rows = result.fetchall()
                return [(row.discord_user_id, row.discord_display_name) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get users by dislike {dislike}: {e}")
            return []

    async def get_users_by_alias(self, alias: str) -> list[tuple[str, str]]:
        """Get Discord users by an alias. Returns empty list if none found.

        The search is case-insensitive and matches any substring.
        For example, searching for "john" would match "john", "johnny", etc.

        Returns:
            List of tuples containing (discord_user_id, discord_display_name)
        """
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT DISTINCT u.discord_user_id, u.discord_display_name
                        FROM users u
                        JOIN user_aliases a ON u.id = a.user_id
                        WHERE a.alias ILIKE :pattern
                    """
                    ),
                    {"pattern": f"%{alias}%"},
                )
                rows = result.fetchall()
                return [(row.discord_user_id, row.discord_display_name) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get users by alias {alias}: {e}")
            return []

    def format_profile_summary(self, profile: dict[str, Any]) -> str:
        """Format user profile into a readable summary string."""
        tone = profile.get("tone", "neutral")
        likes = profile.get("likes", [])
        dislikes = profile.get("dislikes", [])
        aliases = profile.get("aliases", [])
        display_name = profile.get("discord_display_name", "Unknown")

        return f"Display Name: {display_name}, Tone: {tone}, Likes: {likes}, Dislikes: {dislikes}, Aliases: {aliases}"

    def format_profile_for_prompt(self, profile: dict[str, Any]) -> str:
        """Format user profile for system prompt display."""
        likes = profile.get("likes", [])
        dislikes = profile.get("dislikes", [])
        aliases = profile.get("aliases", [])
        display_name = profile.get("discord_display_name", "Unknown")

        parts = [f"- Display name: {display_name}"]

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
