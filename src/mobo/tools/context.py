"""Context management for Discord tools."""

import logging
from typing import Optional, Any
import discord

logger = logging.getLogger(__name__)

# Global Discord context
_discord_context: dict[str, Any] = {}


def set_discord_context(
    guild_member: discord.Member,
    guild_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    message_author_id: Optional[str] = None,
) -> None:
    """Set Discord context for tools to use."""
    global _discord_context
    _discord_context = {
        "guild_member": guild_member,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_author_id": message_author_id,
    }
    logger.debug(
        f"🔧 SET Discord context - guild: {guild_id}, channel: {channel_id}, author: {message_author_id}"
    )


def get_discord_context() -> Optional[dict[str, Any]]:
    """Get Discord context for tools."""
    global _discord_context
    context = _discord_context if _discord_context else None
    logger.debug(
        f"🔍 GET Discord context - available: {context is not None}, channel_id: {context.get('channel_id') if context else 'N/A'}"
    )
    return context
