"""
State definitions for the LangGraph workflow.

The BotState TypedDict defines all data that flows through the bot's workflow,
providing explicit state management and easy debugging.
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


class BotState(TypedDict):
    """
    Simplified state object that flows through the LangGraph workflow.

    Contains only the essential data needed for the bot to process messages,
    make decisions, execute tools, and generate responses.
    """

    # =============================================================================
    # INPUT DATA (Set at workflow start)
    # =============================================================================

    user_message: str
    """The original message from the Discord user"""

    user_id: str
    """Discord user ID as string"""

    channel_id: str
    """Discord channel ID as string"""

    timestamp: datetime
    """When the message was sent"""

    # =============================================================================
    # CONTEXT DATA (Loaded during context phase)
    # =============================================================================

    user_context: Dict[str, Any]
    """User context data (response_tone, likes, dislikes, etc.)"""

    conversation_context: List[Dict[str, Any]]
    """Conversation history from RAG (recent + semantically relevant messages)"""

    # =============================================================================
    # LANGGRAPH STATE (Set by chatbot node)
    # =============================================================================

    messages: List[Any]
    """Messages for LangGraph routing and tool execution"""

    # =============================================================================
    # RESPONSE GENERATION (Set by message generator node)
    # =============================================================================

    final_response: Optional[str]
    """The final text response to send to Discord (None if bot should stay silent)"""

    # =============================================================================
    # METADATA (For monitoring and debugging)
    # =============================================================================

    model_calls: int
    """Number of LLM API calls made"""

    extracted_artifacts: List[Dict[str, Any]]
    """Tool artifacts extracted for Discord upload (images, files, etc.)"""


def format_state_summary(state: BotState) -> str:
    """
    Create a human-readable summary of the state for debugging.

    Args:
        state: The bot state to summarize

    Returns:
        Multi-line string summary of the state
    """
    lines = [
        f"🗨️  Message: {state['user_message'][:50]}{'...' if len(state['user_message']) > 50 else ''}",
        f"👤 User: {state['user_id']} in #{state['channel_id']}",
        f"🤖 Chatbot: {len(state.get('messages', []))} messages generated",
        f"💬 Response: {state['final_response'][:100] if state['final_response'] else 'None'}{'...' if state['final_response'] and len(state['final_response']) > 100 else ''}",
        f"🔄 Model Calls: {state['model_calls']}",
    ]

    return "\n".join(lines)
