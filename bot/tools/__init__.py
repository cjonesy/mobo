"""
Bot tools and capabilities.

This module contains all the tools that the bot can use to interact with
external services, Discord features, and generate content.
"""

from .discord_context import (
    set_discord_context,
    get_discord_context,
)

# Import all tool modules to trigger registration
from . import discord_tools  # noqa
from . import openai_tools  # noqa
from . import giphy_tools  # noqa
from . import web_search_tools  # noqa

from .common import get_all_tools

# Main exports for the tools module
__all__ = [
    # Discord context
    "set_discord_context",
    "get_discord_context",
    # Tools
    "get_all_tools",
]
