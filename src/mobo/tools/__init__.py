"""Tools for the Discord bot agent."""

from .discord_tools import (
    change_nickname,
    get_current_chat_users,
    mention_user,
    mention_message_author,
)
from .image_generation import generate_image
from .user_profile_tools import (
    update_user_tone,
    add_user_interests,
    remove_user_interests,
    get_user_profile,
)
from .context import set_discord_context, get_discord_context

# Export all tools for easy access
__all__ = [
    "change_nickname",
    "get_current_chat_users",
    "mention_user",
    "mention_message_author",
    "generate_image",
    "update_user_tone",
    "add_user_interests",
    "remove_user_interests",
    "get_user_profile",
    "set_discord_context",
    "get_discord_context",
]


def get_all_tools():
    """Get all available tools for the LangChain agent."""
    return [
        generate_image,
        change_nickname,
        get_current_chat_users,
        mention_user,
        mention_message_author,
        update_user_tone,
        add_user_interests,
        remove_user_interests,
        get_user_profile,
    ]
