"""User profile management tools."""

import logging
from typing import Optional

from langchain_core.tools import tool

from ..agent.user_profiles import UserProfileManager

logger = logging.getLogger(__name__)

# Global user profile manager instance
_user_profile_manager: Optional[UserProfileManager] = None


def _get_user_profile_manager() -> UserProfileManager:
    """Get or create user profile manager instance."""
    global _user_profile_manager
    if _user_profile_manager is None:
        _user_profile_manager = UserProfileManager()
    return _user_profile_manager


@tool
async def update_user_tone(user_id: str, tone: str) -> str:
    """Internal tool: Update user's interaction tone based on conversation analysis.

    This tool should ONLY be called when the AI detects tone patterns from natural
    conversation - never in response to direct user requests to change their tone.

    Args:
        user_id: Discord user ID
        tone: Detected tone (friendly, rude, neutral, etc.)

    Returns:
        Status message for internal logging
    """
    try:
        user_manager = _get_user_profile_manager()
        await user_manager.update_user_tone(user_id, tone)

        logger.info(f"Updated tone for user {user_id} to {tone}")
        return f"SUCCESS: User tone updated to {tone}"

    except Exception as e:
        logger.error(f"Error updating user tone: {e}")
        return f"ERROR: Failed to update user tone: {str(e)}"


@tool
async def add_user_interests(
    user_id: str, interests: str, interest_type: str = "likes"
) -> str:
    """Internal tool: Automatically add interests detected from user conversation.

    This tool should ONLY be called when the AI detects new interests from natural
    conversation - never in response to direct user requests to manage interests.

    Args:
        user_id: Discord user ID
        interests: Comma-separated list of interests detected from conversation
        interest_type: Either 'likes' or 'dislikes'

    Returns:
        Status message for internal logging
    """
    try:
        user_manager = _get_user_profile_manager()
        interest_list = [interest.strip() for interest in interests.split(",")]

        if interest_type.lower() == "likes":
            await user_manager.add_user_likes(user_id, interest_list)
            logger.info(f"Added likes for user {user_id}: {interest_list}")
            return f"SUCCESS: Added {', '.join(interest_list)} to user likes"
        elif interest_type.lower() == "dislikes":
            await user_manager.add_user_dislikes(user_id, interest_list)
            logger.info(f"Added dislikes for user {user_id}: {interest_list}")
            return f"SUCCESS: Added {', '.join(interest_list)} to user dislikes"
        else:
            return "ERROR: Invalid interest type (must be 'likes' or 'dislikes')"

    except Exception as e:
        logger.error(f"Error adding user interests: {e}")
        return f"ERROR: Failed to add user interests: {str(e)}"


@tool
async def remove_user_interests(
    user_id: str, interests: str, interest_type: str = "likes"
) -> str:
    """Internal tool: Remove interests when user indicates changed preferences.

    This tool should ONLY be called when the AI detects the user no longer likes/dislikes
    something based on natural conversation - never for direct interest management.

    Args:
        user_id: Discord user ID
        interests: Comma-separated list of interests to remove based on conversation
        interest_type: Either 'likes' or 'dislikes'

    Returns:
        Status message for internal logging
    """
    try:
        user_manager = _get_user_profile_manager()
        interest_list = [interest.strip() for interest in interests.split(",")]

        if interest_type.lower() == "likes":
            await user_manager.remove_user_likes(user_id, interest_list)
            logger.info(f"Removed likes for user {user_id}: {interest_list}")
            return f"SUCCESS: Removed {', '.join(interest_list)} from user likes"
        elif interest_type.lower() == "dislikes":
            await user_manager.remove_user_dislikes(user_id, interest_list)
            logger.info(f"Removed dislikes for user {user_id}: {interest_list}")
            return f"SUCCESS: Removed {', '.join(interest_list)} from user dislikes"
        else:
            return "ERROR: Invalid interest type (must be 'likes' or 'dislikes')"

    except Exception as e:
        logger.error(f"Error removing user interests: {e}")
        return f"ERROR: Failed to remove user interests: {str(e)}"


@tool
async def get_user_profile(user_id: str) -> str:
    """Get a user's profile information to provide personalized responses.

    This can be used when users ask about their preferences or when the AI needs
    context for personalized responses.

    Args:
        user_id: Discord user ID

    Returns:
        User profile information
    """
    try:
        user_manager = _get_user_profile_manager()
        profile = await user_manager.get_user_profile(user_id)

        tone = profile.get("tone", "neutral")
        likes = profile.get("likes", [])
        dislikes = profile.get("dislikes", [])

        profile_text = f"User interaction style: {tone}"
        if likes:
            profile_text += f"\nLikes: {', '.join(likes[:5])}"
        if dislikes:
            profile_text += f"\nDislikes: {', '.join(dislikes[:5])}"

        return profile_text

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return f"ERROR: Failed to retrieve user profile: {str(e)}"
