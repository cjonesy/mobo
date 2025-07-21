"""
Dependencies for Discord bot tools using memory management.
"""

from typing import Optional
from pydantic import BaseModel
import discord

from ..memory_manager import MemoryManager


class BotDependencies(BaseModel):
    """Dependencies passed to all bot tools and functions."""

    memory: MemoryManager
    user_id: str
    channel_id: str
    discord_client: Optional[discord.Client] = None
    guild_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
