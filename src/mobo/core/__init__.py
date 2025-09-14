"""
Core bot logic using modern LangGraph patterns.

This module contains the LangGraph workflow implementation using
standard conditional routing and built-in tool execution.
"""

from .workflow import create_bot_workflow, execute_workflow, create_workflow_for_message
from .state import BotState

# Main exports for the core module
__all__ = [
    # Workflow
    "create_bot_workflow",
    "execute_workflow",
    "create_workflow_for_message",
    # State management
    "BotState",
]
