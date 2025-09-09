"""
Discord Bot Package

A Discord bot with LangGraph supervisor pattern for intelligent tool orchestration.
"""

__version__ = "0.1.0"

from .config import get_settings

__all__ = [
    "__version__",
    "get_settings",
]
