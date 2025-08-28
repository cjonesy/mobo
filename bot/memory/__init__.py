"""
Memory management module for the Discord bot.

This module provides comprehensive memory capabilities including:
- Conversation storage and retrieval with vector embeddings
- User profile management and behavioral analysis
- Intelligent RAG-based context retrieval
"""

from .langgraph_memory import LangGraphMemory, get_config_for_thread
from .models import Base, Conversation, User, UserLike, UserDislike, UserAlias

__all__ = [
    # Modern LangGraph 2025 memory patterns
    "LangGraphMemory",
    "get_config_for_thread",
    # Legacy database models (for migration compatibility)
    "Base",
    "Conversation", 
    "User",
    "UserLike",
    "UserDislike",
    "UserAlias",
]
