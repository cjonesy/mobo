"""Tools for looking up user information from the database."""

import logging
from typing import Any

from langchain.tools import BaseTool
from pydantic import Field

from ..agent.user_profiles import UserProfileManager

logger = logging.getLogger(__name__)


class SearchUsersByLikeTool(BaseTool):
    """Tool for finding users who like something."""

    name: str = "search_users_by_like"
    description: str = (
        "Find users who like something specific. Input should be what you want to search for (e.g. 'cats')."
    )
    user_profile_manager: UserProfileManager = Field(default_factory=UserProfileManager)

    async def _arun(self, term: str) -> str:
        """Run the tool asynchronously."""
        try:
            users = await self.user_profile_manager.get_users_by_like(term)
            if not users:
                return f"No users found who like '{term}'."

            return "\n".join(
                f"{display_name} (ID: {user_id})" for user_id, display_name in users
            )

        except Exception as e:
            logger.error(f"Error searching users by like '{term}': {e}")
            return f"Error searching users: {str(e)}"

    def _run(self, term: str) -> str:
        """Synchronous version is not supported."""
        raise NotImplementedError("This tool only supports async operations")


class SearchUsersByDislikeTool(BaseTool):
    """Tool for finding users who dislike something."""

    name: str = "search_users_by_dislike"
    description: str = (
        "Find users who dislike something specific. Input should be what you want to search for (e.g. 'spam')."
    )
    user_profile_manager: UserProfileManager = Field(default_factory=UserProfileManager)

    async def _arun(self, term: str) -> str:
        """Run the tool asynchronously."""
        try:
            users = await self.user_profile_manager.get_users_by_dislike(term)
            if not users:
                return f"No users found who dislike '{term}'."

            return "\n".join(
                f"{display_name} (ID: {user_id})" for user_id, display_name in users
            )

        except Exception as e:
            logger.error(f"Error searching users by dislike '{term}': {e}")
            return f"Error searching users: {str(e)}"

    def _run(self, term: str) -> str:
        """Synchronous version is not supported."""
        raise NotImplementedError("This tool only supports async operations")


class SearchUsersByAliasTool(BaseTool):
    """Tool for finding users by alias."""

    name: str = "search_users_by_alias"
    description: str = (
        "Find users by searching their aliases. Input should be the alias to search for."
    )
    user_profile_manager: UserProfileManager = Field(default_factory=UserProfileManager)

    async def _arun(self, term: str) -> str:
        """Run the tool asynchronously."""
        try:
            users = await self.user_profile_manager.get_users_by_alias(term)
            if not users:
                return f"No users found with alias matching '{term}'."

            return "\n".join(
                f"{display_name} (ID: {user_id})" for user_id, display_name in users
            )

        except Exception as e:
            logger.error(f"Error searching users by alias '{term}': {e}")
            return f"Error searching users: {str(e)}"

    def _run(self, term: str) -> str:
        """Synchronous version is not supported."""
        raise NotImplementedError("This tool only supports async operations")


class GetUserProfileTool(BaseTool):
    """Tool for getting a user's full profile."""

    name: str = "get_user_profile"
    description: str = (
        "Get detailed profile information for a user. Input should be the user's Discord ID."
    )
    user_profile_manager: UserProfileManager = Field(default_factory=UserProfileManager)

    async def _arun(self, discord_user_id: str) -> str:
        """Run the tool asynchronously."""
        try:
            profile = await self.user_profile_manager.get_user_profile(discord_user_id)
            return self.user_profile_manager.format_profile_summary(profile)

        except Exception as e:
            logger.error(f"Error getting user profile for '{discord_user_id}': {e}")
            return f"Error getting user profile: {str(e)}"

    def _run(self, discord_user_id: str) -> str:
        """Synchronous version is not supported."""
        raise NotImplementedError("This tool only supports async operations")
