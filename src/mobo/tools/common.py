"""
Common utilities and tool registry for bot tools.

Tools receive runtime context via LangGraph's RunnableConfig mechanism.
"""

import logging
from typing import List, Any, Optional
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger(__name__)


# Global tool registry
_TOOL_REGISTRY: List[Any] = []


def get_all_tools() -> List[Any]:
    """Get all registered tools.

    Returns:
        List of all tools that have been registered
    """
    return _TOOL_REGISTRY.copy()


def registered_tool(name: Optional[str] = None, **langchain_kwargs):
    """
    Decorator that creates a LangChain tool.

    Tools can access runtime context (Discord client, message, etc.)
    via the RunnableConfig parameter.

    Args:
        name: Optional name for the tool. If not provided, uses the function name
        **langchain_kwargs: Additional kwargs to pass to the LangChain tool decorator

    Example:
        @registered_tool()
        async def my_tool(param: str, config: RunnableConfig) -> str:
            # Access Discord context from config
            client = config["configurable"]["discord_client"]
            message = config["configurable"]["discord_message"]
            return f"Hello from {message.author.display_name}: {param}"
    """

    def decorator(func):
        # Apply LangChain's tool decorator directly
        langchain_decorated = langchain_tool(parse_docstring=True, **langchain_kwargs)(
            func
        )

        # Set the tool name if provided
        if name:
            langchain_decorated.name = name

        # Add to registry
        _TOOL_REGISTRY.append(langchain_decorated)
        logger.debug(f"Registered tool '{langchain_decorated.name}'")

        return langchain_decorated

    return decorator
