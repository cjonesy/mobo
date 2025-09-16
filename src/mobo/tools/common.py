"""
Common utilities and tool registry for bot tools.

Tools receive runtime context via LangGraph's RunnableConfig mechanism.
Now using LangChain's native tool decorator with auto-discovery.
"""

import logging
from typing import List, Any

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
