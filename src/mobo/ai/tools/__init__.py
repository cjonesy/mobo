"""
PydanticAI tools for Discord bot functionality.

This module organizes tools into separate files for better maintainability.
Each tool is in its own file under the tools/ directory.
"""

from typing import Any, List

# Import all tools and dependencies
from .dependencies import BotDependencies
from .user_profile import (
    update_conversation_style,
    add_topics,
    remove_topics,
    get_topics,
)
from .conversation_history import search_conversation_history
from .image_generation import generate_image
from .bot_profile import update_bot_nickname, get_bot_nickname, update_bot_avatar
from .discord import list_chat_users, get_channel_topic, mention_user

# Export only the main interfaces
__all__ = [
    "BotDependencies",
    "get_discord_tools",
]


def get_discord_tools() -> List[Any]:
    """Get all tools for Discord bot functionality.

    Returns:
        List of tool functions that can be registered with a PydanticAI agent
    """
    return [
        search_conversation_history,
        update_conversation_style,
        add_topics,
        remove_topics,
        get_topics,
        generate_image,
        update_bot_nickname,
        get_bot_nickname,
        update_bot_avatar,
        list_chat_users,
        get_channel_topic,
        mention_user,
        # Add more tools here as needed
    ]
