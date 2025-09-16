"""
User repository for database operations.

This repository handles all database operations related to users,
their profiles, likes, dislikes, and aliases.
"""

from typing import Optional, Sequence, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import AsyncRepository
from ..models.user import User, UserLike, UserDislike, UserAlias


class UserRepository(AsyncRepository[User]):
    """Repository for User model operations."""

    def __init__(self):
        super().__init__(User)

    async def get_by_discord_id(
        self, session: AsyncSession, discord_user_id: str
    ) -> Optional[User]:
        """Get user by Discord ID with all relationships loaded."""
        stmt = (
            select(User)
            .where(User.discord_user_id == discord_user_id)
            .options(
                selectinload(User.likes),
                selectinload(User.dislikes),
                selectinload(User.aliases),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self, session: AsyncSession, discord_user_id: str, **kwargs
    ) -> User:
        """Create a new user with default values."""
        user_data = {
            "discord_user_id": discord_user_id,
            "response_tone": kwargs.get("response_tone", "neutral"),
            **kwargs,
        }

        user = User(**user_data)
        session.add(user)
        await session.flush()  # Get the user with ID
        return user

    async def update_response_tone(
        self, session: AsyncSession, discord_user_id: str, tone: str
    ) -> Optional[User]:
        """Update user's response tone preference."""
        user = await self.get_by_discord_id(session, discord_user_id)
        if user:
            user.response_tone = tone
            await session.flush()
        return user

    async def get_like(
        self,
        session: AsyncSession,
        discord_user_id: str,
        like_term: str,
    ) -> Optional[UserLike]:
        """Get existing like for a user and term."""
        stmt = select(UserLike).where(
            UserLike.user_id == discord_user_id, UserLike.like_term == like_term
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_like(
        self,
        session: AsyncSession,
        discord_user_id: str,
        like_term: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> UserLike:
        """Create a new like record."""
        like = UserLike(
            user_id=discord_user_id,
            like_term=like_term,
            confidence=confidence,
            source=source,
        )
        session.add(like)
        await session.flush()
        return like

    async def update_like(
        self,
        session: AsyncSession,
        like: UserLike,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
    ) -> UserLike:
        """Update an existing like record."""
        if confidence is not None:
            like.confidence = confidence
        if source is not None:
            like.source = source
        await session.flush()
        return like

    async def get_dislike(
        self,
        session: AsyncSession,
        discord_user_id: str,
        dislike_term: str,
    ) -> Optional[UserDislike]:
        """Get existing dislike for a user and term."""
        stmt = select(UserDislike).where(
            UserDislike.user_id == discord_user_id,
            UserDislike.dislike_term == dislike_term,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_dislike(
        self,
        session: AsyncSession,
        discord_user_id: str,
        dislike_term: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> UserDislike:
        """Create a new dislike record."""
        dislike = UserDislike(
            user_id=discord_user_id,
            dislike_term=dislike_term,
            confidence=confidence,
            source=source,
        )
        session.add(dislike)
        await session.flush()
        return dislike

    async def update_dislike(
        self,
        session: AsyncSession,
        dislike: UserDislike,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
    ) -> UserDislike:
        """Update an existing dislike record."""
        if confidence is not None:
            dislike.confidence = confidence
        if source is not None:
            dislike.source = source
        await session.flush()
        return dislike

    async def add_alias(
        self,
        session: AsyncSession,
        discord_user_id: str,
        alias: str,
        is_preferred: bool = False,
        source: Optional[str] = None,
    ) -> Optional[UserAlias]:
        """Add an alias for a user, avoiding duplicates."""
        # Check if alias already exists
        stmt = select(UserAlias).where(
            UserAlias.user_id == discord_user_id, UserAlias.alias == alias
        )
        result = await session.execute(stmt)
        existing_alias = result.scalar_one_or_none()

        if existing_alias:
            # Update preferred status if needed
            if is_preferred and not existing_alias.is_preferred:
                existing_alias.is_preferred = True
                existing_alias.source = source
                await session.flush()
            return existing_alias

        # Create new alias
        alias_obj = UserAlias(
            user_id=discord_user_id,
            alias=alias,
            is_preferred=is_preferred,
            source=source,
        )
        session.add(alias_obj)
        await session.flush()
        return alias_obj

    async def remove_like(
        self, session: AsyncSession, discord_user_id: str, like_term: str
    ) -> bool:
        """Remove a like for a user."""
        stmt = delete(UserLike).where(
            UserLike.user_id == discord_user_id, UserLike.like_term == like_term
        )
        result = await session.execute(stmt)
        return result.rowcount > 0

    async def remove_dislike(
        self, session: AsyncSession, discord_user_id: str, dislike_term: str
    ) -> bool:
        """Remove a dislike for a user."""
        stmt = delete(UserDislike).where(
            UserDislike.user_id == discord_user_id,
            UserDislike.dislike_term == dislike_term,
        )
        result = await session.execute(stmt)
        return result.rowcount > 0

    async def get_user_likes(
        self, session: AsyncSession, discord_user_id: str
    ) -> Sequence[UserLike]:
        """Get all likes for a user."""
        stmt = (
            select(UserLike)
            .where(UserLike.user_id == discord_user_id)
            .order_by(UserLike.confidence.desc(), UserLike.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_user_dislikes(
        self, session: AsyncSession, discord_user_id: str
    ) -> Sequence[UserDislike]:
        """Get all dislikes for a user."""
        stmt = (
            select(UserDislike)
            .where(UserDislike.user_id == discord_user_id)
            .order_by(UserDislike.confidence.desc(), UserDislike.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_preferred_alias(
        self, session: AsyncSession, discord_user_id: str
    ) -> Optional[str]:
        """Get user's preferred alias if any."""
        stmt = (
            select(UserAlias)
            .where(UserAlias.user_id == discord_user_id, UserAlias.is_preferred)
            .order_by(UserAlias.created_at.desc())
        )
        result = await session.execute(stmt)
        alias = result.scalar_one_or_none()
        return str(alias.alias) if alias else None

    async def get_user_profile_dict(
        self, session: AsyncSession, discord_user_id: str
    ) -> Dict[str, Any]:
        """Get user profile as a dictionary for easy consumption by services."""
        user = await self.get_by_discord_id(session, discord_user_id)

        if not user:
            return {
                "discord_user_id": discord_user_id,
                "response_tone": "neutral",
                "likes": [],
                "dislikes": [],
                "aliases": [],
                "preferred_alias": None,
                "exists": False,
            }

        return {
            "discord_user_id": user.discord_user_id,
            "response_tone": user.response_tone,
            "last_seen": user.last_seen,
            "likes": [
                {
                    "term": like.like_term,
                    "confidence": like.confidence,
                    "source": like.source,
                }
                for like in user.likes
            ],
            "dislikes": [
                {
                    "term": dislike.dislike_term,
                    "confidence": dislike.confidence,
                    "source": dislike.source,
                }
                for dislike in user.dislikes
            ],
            "aliases": [
                {
                    "alias": alias.alias,
                    "is_preferred": alias.is_preferred,
                    "source": alias.source,
                }
                for alias in user.aliases
            ],
            "preferred_alias": next(
                (alias.alias for alias in user.aliases if alias.is_preferred), None
            ),
            "exists": True,
        }
