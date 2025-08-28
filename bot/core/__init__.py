"""
Core bot logic using modern LangGraph patterns.

This module contains the LangGraph workflow implementation using
standard conditional routing and built-in tool execution.
"""

from .workflow import create_bot_workflow, execute_workflow
from .state import BotState, create_initial_state
from .response_extractor import response_extractor_node

# Main exports for the core module
__all__ = [
    # Workflow
    "create_bot_workflow",
    "execute_workflow",
    # State management
    "BotState",
    "create_initial_state",
    # Core components
    "response_extractor_node",
]
