"""Tools for the Discord bot agent."""

from .discord_tools import (
    change_nickname,
    get_current_chat_users,
    mention_user,
    mention_message_author,
    generate_and_set_profile_picture,
)
from .image_generation import generate_image
from .context import set_discord_context, get_discord_context
from .giphy_tools import SearchGiphyTool
from .user_lookup import (
    SearchUsersByLikeTool,
    SearchUsersByDislikeTool,
    SearchUsersByAliasTool,
    GetUserProfileTool,
)

# Export all tools for easy access
__all__ = [
    "change_nickname",
    "get_current_chat_users",
    "mention_user",
    "mention_message_author",
    "generate_and_set_profile_picture",
    "generate_image",
    "set_discord_context",
    "get_discord_context",
    "SearchGiphyTool",
    "SearchUsersByLikeTool",
    "SearchUsersByDislikeTool",
    "SearchUsersByAliasTool",
    "GetUserProfileTool",
]


def get_all_tools():
    """Get all available tools for the LangChain agent."""
    return [
        generate_image,
        generate_and_set_profile_picture,
        change_nickname,
        get_current_chat_users,
        mention_user,
        mention_message_author,
        SearchGiphyTool(),
        SearchUsersByLikeTool(),
        SearchUsersByDislikeTool(),
        SearchUsersByAliasTool(),
        GetUserProfileTool(),
    ]
