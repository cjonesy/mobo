"""
Discord context management for tools.

This module handles passing Discord context (message, channel, guild, etc.)
to tools so they can interact with Discord properly.
"""

import logging
import threading
from typing import Optional
from dataclasses import dataclass
from contextlib import contextmanager

import discord

logger = logging.getLogger(__name__)


@dataclass
class DiscordContext:
    """Discord context information for tool execution."""

    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    user_id: Optional[str] = None
    client_user: Optional[discord.ClientUser] = None
    message: Optional[discord.Message] = None
    client: Optional[discord.Client] = None


# Thread-local storage for Discord context
_thread_local = threading.local()


def get_discord_context() -> Optional[DiscordContext]:
    """Get current Discord context for tool usage."""
    return getattr(_thread_local, "discord_context", None)


@contextmanager
def discord_context_manager(context: DiscordContext):
    """
    Context manager for setting Discord context in the current thread.

    This ensures that each workflow execution has its own isolated context
    and automatically cleans up when done.
    """
    _thread_local.discord_context = context
    logger.debug(
        f"🔧 Discord context set for guild {context.guild_id}, channel {context.channel_id}"
    )
    try:
        yield context
    finally:
        _thread_local.discord_context = None
        logger.debug("🧹 Discord context cleared")
