"""
Discord context management for tools.

This module handles passing Discord context (message, channel, guild, etc.)
to tools so they can interact with Discord properly.
"""

import logging
from typing import Optional
from dataclasses import dataclass

import discord

logger = logging.getLogger(__name__)


@dataclass
class DiscordContext:
    """Discord context information for tool execution."""

    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    user_id: Optional[str] = None
    message_author_id: Optional[str] = None
    client_user: Optional[discord.ClientUser] = None
    message: Optional[discord.Message] = None
    client: Optional[discord.Client] = None


# Global context storage - shared across all tools
_discord_context: Optional[DiscordContext] = None


def set_discord_context(
    guild_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    user_id: Optional[str] = None,
    message_author_id: Optional[str] = None,
    client_user: Optional[discord.ClientUser] = None,
    message: Optional[discord.Message] = None,
    client: Optional[discord.Client] = None,
) -> None:
    """
    Set the current Discord context for tool execution.

    This context is used by all tools that need to interact with Discord
    (reactions, nickname changes, etc.).

    Args:
        guild_id: Discord guild (server) ID
        channel_id: Discord channel ID
        user_id: Discord user ID (bot's ID)
        message_author_id: ID of the user who sent the message
        client_user: Discord ClientUser object (bot's user)
        message: Discord Message object being responded to
    """
    global _discord_context

    _discord_context = DiscordContext(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=user_id,
        message_author_id=message_author_id,
        client_user=client_user,
        message=message,
        client=client,
    )
    logger.debug(
        f"🔧 Discord context updated for guild {guild_id}, channel {channel_id}"
    )


def get_discord_context() -> Optional[DiscordContext]:
    """Get current Discord context for tool usage."""
    return _discord_context


def clear_discord_context() -> None:
    """Clear the current Discord context."""
    global _discord_context
    _discord_context = None
    logger.debug("🧹 Discord context cleared")
