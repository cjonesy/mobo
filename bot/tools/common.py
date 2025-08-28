"""
Common utilities and tool registry for bot tools.

Simple tool registry where tools can register themselves.
"""

import logging
from functools import wraps
from typing import List, Any, Callable, TypeVar, Optional
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)

# Global tool registry
_TOOL_REGISTRY: List[Any] = []


def get_all_tools() -> List[Any]:
    """Get all registered tools.

    Returns:
        List of all tools that have been registered
    """
    return _TOOL_REGISTRY.copy()


# Utility functions
def validate_api_key(api_key: str, service_name: str) -> None:
    """Validate that an API key is configured and not empty."""
    if not api_key or api_key.strip() == "":
        raise ValueError(f"{service_name} API key not configured")


def safe_truncate(text: str, max_length: int = 100) -> str:
    """Safely truncate text for logging purposes."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def registered_tool(name: Optional[str] = None, **langchain_kwargs):
    """
    Decorator that creates a LangChain tool and adds it to the bot's registry.

    Args:
        name: Optional name for the tool. If not provided, uses the function name
        **langchain_kwargs: Additional kwargs to pass to the LangChain tool decorator
    """

    def decorator(func: F) -> F:
        # Apply LangChain's tool decorator first

        langchain_decorated = langchain_tool(**langchain_kwargs)(func)

        # Add to registry
        _TOOL_REGISTRY.append(langchain_decorated)
        logger.debug(f"Registered tool '{langchain_decorated.name}'")

        return langchain_decorated

    return decorator
