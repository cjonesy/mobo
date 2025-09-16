"""
Bot tools and capabilities.

This module contains all the tools that the bot can use to interact with
external services, Discord features, and generate content.
"""

# Import all tool modules to trigger registration
from . import discord_tools  # noqa
from . import openai_tools  # noqa
from . import giphy_tools  # noqa
from . import web_tools  # noqa

from .common import get_all_tools

# Main exports for the tools module
__all__ = [
    "get_all_tools",
]
