"""
User service for business logic operations.

This service handles all user-related business logic, including profile management,
preferences, likes/dislikes, and aliases. It coordinates between the UserRepository
and provides high-level operations for the application.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, UTC

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related business operations."""

    def __init__(self):
        self.user_repo = UserRepository()

    async def get_or_create_user(
        self, session: AsyncSession, discord_user_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Get existing user or create a new one with default preferences.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            **kwargs: Additional user data

        Returns:
            User profile dictionary
        """
        try:
            # Try to get existing user
            user_profile = await self.user_repo.get_user_profile_dict(
                session, discord_user_id
            )

            if user_profile["exists"]:
                logger.debug(f"Retrieved existing user profile for {discord_user_id}")
                return user_profile

            # Create new user
            await self.user_repo.create_user(session, discord_user_id, **kwargs)
            await session.commit()

            logger.info(f"Created new user profile for {discord_user_id}")

            # Return the new user profile
            return await self.user_repo.get_user_profile_dict(session, discord_user_id)

        except Exception as e:
            logger.error(f"Error getting/creating user {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def update_user_preferences(
        self,
        session: AsyncSession,
        discord_user_id: str,
        response_tone: Optional[str] = None,
        **other_updates,
    ) -> Optional[Dict[str, Any]]:
        """
        Update user preferences.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            response_tone: New response tone preference
            **other_updates: Other user fields to update

        Returns:
            Updated user profile dictionary or None if user not found
        """
        try:
            # Ensure user exists
            user_profile = await self.get_or_create_user(session, discord_user_id)

            updates_made = False

            if response_tone is not None:
                user = await self.user_repo.update_response_tone(
                    session, discord_user_id, response_tone
                )
                if user:
                    updates_made = True
                    logger.debug(
                        f"Updated response tone for {discord_user_id} to {response_tone}"
                    )

            # Handle other updates if needed
            if other_updates:
                # For now, we'll just log them - extend as needed
                logger.debug(
                    f"Additional updates for {discord_user_id}: {other_updates}"
                )

            if updates_made:
                await session.commit()
                return await self.user_repo.get_user_profile_dict(
                    session, discord_user_id
                )
            else:
                return user_profile

        except Exception as e:
            logger.error(f"Error updating preferences for {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def add_user_like(
        self,
        session: AsyncSession,
        discord_user_id: str,
        like_term: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> bool:
        """
        Add a like for a user.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            like_term: What the user likes
            confidence: Confidence level (0.0-1.0)
            source: How this was learned (e.g., 'explicit', 'inferred')

        Returns:
            True if like was added/updated, False otherwise
        """
        try:
            # Ensure user exists
            await self.get_or_create_user(session, discord_user_id)

            # Validate confidence
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("Confidence must be between 0.0 and 1.0")

            # Add the like
            like = await self.user_repo.add_like(
                session, discord_user_id, like_term, confidence, source
            )

            if like:
                await session.commit()
                logger.info(f"Added like '{like_term}' for user {discord_user_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error adding like for {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def add_user_dislike(
        self,
        session: AsyncSession,
        discord_user_id: str,
        dislike_term: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> bool:
        """
        Add a dislike for a user.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            dislike_term: What the user dislikes
            confidence: Confidence level (0.0-1.0)
            source: How this was learned

        Returns:
            True if dislike was added/updated, False otherwise
        """
        try:
            # Ensure user exists
            await self.get_or_create_user(session, discord_user_id)

            # Validate confidence
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("Confidence must be between 0.0 and 1.0")

            result = await self.add_dislike(
                session, discord_user_id, dislike_term, confidence, source
            )

            if result["action"] in ["created", "updated"]:
                logger.info(
                    f"{result['action'].title()} dislike '{dislike_term}' for user {discord_user_id}"
                )
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error adding dislike for {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def add_user_alias(
        self,
        session: AsyncSession,
        discord_user_id: str,
        alias: str,
        is_preferred: bool = False,
        source: Optional[str] = None,
    ) -> bool:
        """
        Add an alias for a user.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            alias: The alias/nickname
            is_preferred: Whether this is their preferred name
            source: How this was learned

        Returns:
            True if alias was added/updated, False otherwise
        """
        try:
            # Ensure user exists
            await self.get_or_create_user(session, discord_user_id)

            # Add the alias
            alias_obj = await self.user_repo.add_alias(
                session, discord_user_id, alias, is_preferred, source
            )

            if alias_obj:
                await session.commit()
                logger.info(f"Added alias '{alias}' for user {discord_user_id}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error adding alias for {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def remove_user_like(
        self, session: AsyncSession, discord_user_id: str, like_term: str
    ) -> bool:
        """Remove a like for a user."""
        try:
            success = await self.user_repo.remove_like(
                session, discord_user_id, like_term
            )
            if success:
                await session.commit()
                logger.info(f"Removed like '{like_term}' for user {discord_user_id}")
            return success
        except Exception as e:
            logger.error(f"Error removing like for {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def remove_user_dislike(
        self, session: AsyncSession, discord_user_id: str, dislike_term: str
    ) -> bool:
        """Remove a dislike for a user."""
        try:
            success = await self.user_repo.remove_dislike(
                session, discord_user_id, dislike_term
            )
            if success:
                await session.commit()
                logger.info(
                    f"Removed dislike '{dislike_term}' for user {discord_user_id}"
                )
            return success
        except Exception as e:
            logger.error(f"Error removing dislike for {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def get_user_context_for_bot(
        self, session: AsyncSession, discord_user_id: str
    ) -> Dict[str, Any]:
        """
        Get user context formatted for bot consumption.

        This method provides a clean interface for the bot to get user
        information without needing to know about the repository structure.

        Returns:
            Dictionary with user context including preferences, likes, dislikes, etc.
        """
        try:
            user_profile = await self.user_repo.get_user_profile_dict(
                session, discord_user_id
            )

            # Format for bot consumption
            context = {
                "user_id": discord_user_id,
                "response_tone": user_profile.get("response_tone", "neutral"),
                "preferred_name": user_profile.get("preferred_alias"),
                "likes": [like["term"] for like in user_profile.get("likes", [])],
                "dislikes": [
                    dislike["term"] for dislike in user_profile.get("dislikes", [])
                ],
                "high_confidence_likes": [
                    like["term"]
                    for like in user_profile.get("likes", [])
                    if like["confidence"] >= 0.8
                ],
                "high_confidence_dislikes": [
                    dislike["term"]
                    for dislike in user_profile.get("dislikes", [])
                    if dislike["confidence"] >= 0.8
                ],
                "is_new_user": not user_profile.get("exists", False),
            }

            return context

        except Exception as e:
            logger.error(f"Error getting user context for {discord_user_id}: {e}")
            # Return minimal context on error
            return {
                "user_id": discord_user_id,
                "response_tone": "neutral",
                "preferred_name": None,
                "likes": [],
                "dislikes": [],
                "high_confidence_likes": [],
                "high_confidence_dislikes": [],
                "is_new_user": True,
            }

    async def update_last_seen(
        self, session: AsyncSession, discord_user_id: str
    ) -> None:
        """Update the user's last seen timestamp."""
        try:
            user = await self.user_repo.get_by_discord_id(session, discord_user_id)
            if user:
                user.last_seen = datetime.now(UTC)
                await session.commit()
        except Exception as e:
            logger.error(f"Error updating last seen for {discord_user_id}: {e}")
            await session.rollback()

    async def add_like(
        self,
        session: AsyncSession,
        discord_user_id: str,
        like_term: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a like for a user with business logic for duplicates and confidence.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            like_term: Term the user likes
            confidence: Confidence level (0.0-1.0)
            source: Source of the like information

        Returns:
            Dictionary with like information and whether it was created or updated
        """
        try:
            existing_like = await self.user_repo.get_like(
                session, discord_user_id, like_term
            )

            if existing_like:
                # only update if new confidence is higher
                if confidence > existing_like.confidence:
                    like = await self.user_repo.update_like(
                        session, existing_like, confidence, source
                    )
                    await session.commit()
                    logger.debug(
                        f"Updated like '{like_term}' for user {discord_user_id} "
                        f"with confidence {confidence}"
                    )
                    return {"like": like, "action": "updated"}
                else:
                    logger.debug(
                        f"Like '{like_term}' for user {discord_user_id} already exists "
                        f"with higher confidence"
                    )
                    return {"like": existing_like, "action": "no_change"}

            # Create new like
            like = await self.user_repo.create_like(
                session, discord_user_id, like_term, confidence, source
            )
            await session.commit()
            logger.debug(
                f"Added like '{like_term}' for user {discord_user_id} "
                f"with confidence {confidence}"
            )
            return {"like": like, "action": "created"}

        except Exception as e:
            logger.error(f"Error adding like for user {discord_user_id}: {e}")
            await session.rollback()
            raise

    async def add_dislike(
        self,
        session: AsyncSession,
        discord_user_id: str,
        dislike_term: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a dislike for a user with business logic for duplicates and confidence.

        Args:
            session: Database session
            discord_user_id: Discord user ID
            dislike_term: Term the user dislikes
            confidence: Confidence level (0.0-1.0)
            source: Source of the dislike information

        Returns:
            Dictionary with dislike information and whether it was created or updated
        """
        try:
            existing_dislike = await self.user_repo.get_dislike(
                session, discord_user_id, dislike_term
            )

            if existing_dislike:
                # only update if new confidence is higher
                if confidence > existing_dislike.confidence:
                    dislike = await self.user_repo.update_dislike(
                        session, existing_dislike, confidence, source
                    )
                    await session.commit()
                    logger.debug(
                        f"Updated dislike '{dislike_term}' for user {discord_user_id} "
                        f"with confidence {confidence}"
                    )
                    return {"dislike": dislike, "action": "updated"}
                else:
                    logger.debug(
                        f"Dislike '{dislike_term}' for user {discord_user_id} already exists "
                        f"with higher confidence"
                    )
                    return {"dislike": existing_dislike, "action": "no_change"}

            # Create new dislike
            dislike = await self.user_repo.create_dislike(
                session, discord_user_id, dislike_term, confidence, source
            )
            await session.commit()
            logger.debug(
                f"Added dislike '{dislike_term}' for user {discord_user_id} "
                f"with confidence {confidence}"
            )
            return {"dislike": dislike, "action": "created"}

        except Exception as e:
            logger.error(f"Error adding dislike for user {discord_user_id}: {e}")
            await session.rollback()
            raise
