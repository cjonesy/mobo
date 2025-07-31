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
) -> None:
    """Set Discord context for tools to use."""
    global _discord_context
    _discord_context = {
        "guild_member": guild_member,
        "guild_id": guild_id,
        "channel_id": channel_id,
    }
    logger.debug(f"Set Discord context for guild {guild_id}, channel {channel_id}")


def get_discord_context() -> Optional[dict[str, Any]]:
    """Get Discord context for tools."""
    global _discord_context
    return _discord_context if _discord_context else None
