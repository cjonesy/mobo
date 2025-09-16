"""
Common utilities and tool registry for bot tools.

Tools receive runtime context via LangGraph's RunnableConfig mechanism.
Now using LangChain's native tool decorator with auto-registration.
"""

import logging
from typing import List, Any, Callable
from langchain_core.tools import tool as langchain_tool

logger = logging.getLogger(__name__)


# Global tool registry - populated by tool imports
_TOOL_REGISTRY: List[Any] = []


def get_all_tools() -> List[Any]:
    """Get all registered tools.

    Returns:
        List of all tools that have been registered
    """
    return _TOOL_REGISTRY.copy()


def register_tool(tool_instance: Any) -> None:
    """Register a tool instance in the global registry.

    This is called automatically when tools are created with the @tool decorator.

    Args:
        tool_instance: LangChain tool instance to register
    """
    _TOOL_REGISTRY.append(tool_instance)
    logger.debug(f"Registered tool '{tool_instance.name}'")


def tool(*args, **kwargs) -> Callable:
    """Auto-registering tool decorator that wraps LangChain's @tool.

    This decorator automatically registers tools with our global registry
    while preserving all LangChain @tool functionality.

    Usage:
        @tool
        async def my_tool(config: RunnableConfig) -> str:
            return "Hello"

    Args:
        *args, **kwargs: All arguments passed to LangChain's @tool decorator

    Returns:
        Decorated function that's automatically registered
    """

    def decorator(func: Callable) -> Any:
        # Create the LangChain tool instance
        langchain_tool_instance = langchain_tool(func)

        # Auto-register it
        register_tool(langchain_tool_instance)

        return langchain_tool_instance

    def parameterized_decorator(*decorator_args, **decorator_kwargs):
        def inner_decorator(func: Callable) -> Any:
            # Create the LangChain tool instance with parameters
            langchain_tool_instance = langchain_tool(*decorator_args, **decorator_kwargs)(func)

            # Auto-register it
            register_tool(langchain_tool_instance)

            return langchain_tool_instance
        return inner_decorator

    # Handle both @tool and @tool() syntax
    if len(args) == 1 and callable(args[0]) and not kwargs:
        # Direct decoration: @tool
        return decorator(args[0])
    else:
        # Parameterized decoration: @tool() or @tool(name="foo")
        return parameterized_decorator(*args, **kwargs)
