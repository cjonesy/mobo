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

    personality: str
    """The bot's personality prompt"""

    user_profile: Dict[str, Any]
    """User profile data (response_tone, likes, dislikes, etc.)"""

    conversation_history: List[Dict[str, Any]]
    """Recent conversation messages for context"""

    rag_context: str
    """Relevant context retrieved from RAG memory"""

    # =============================================================================
    # LANGGRAPH STATE (Set by chatbot node)
    # =============================================================================

    messages: List[Any]
    """Messages for LangGraph routing and tool execution"""

    # =============================================================================
    # RESPONSE GENERATION (Set by response generator node)
    # =============================================================================

    final_response: str
    """The final text response to send to Discord"""

    # =============================================================================
    # METADATA (For monitoring and debugging)
    # =============================================================================

    execution_time: float
    """Total time spent processing this message (seconds)"""

    model_calls: int
    """Number of LLM API calls made"""

    workflow_path: List[str]
    """List of nodes executed in the workflow"""

    debug_info: Dict[str, Any]
    """Additional debug information"""
    
    extracted_artifacts: List[Dict[str, Any]]
    """Tool artifacts extracted for Discord upload (images, files, etc.)"""


# =============================================================================
# HELPER TYPES FOR SPECIFIC USE CASES
# =============================================================================


class ToolResult(TypedDict):
    """Standardized format for tool execution results."""

    success: bool
    """Whether the tool executed successfully"""

    result: Any
    """The actual result from the tool"""

    summary: Optional[str]
    """Human-readable summary of what the tool accomplished"""

    error: Optional[str]
    """Error message if tool failed"""

    execution_time: float
    """Time taken to execute the tool"""


class UserProfileData(TypedDict):
    """Structure for user profile information."""

    user_id: str
    """Discord user ID"""

    display_name: str
    """User's display name"""

    response_tone: str
    """Bot's response tone for this user (friendly, neutral, hostile, etc.)"""

    likes: List[str]
    """Things the user likes"""

    dislikes: List[str]
    """Things the user dislikes"""

    aliases: List[str]
    """Alternative names the user wants to be called"""

    last_seen: datetime
    """When user was last active"""


class ConversationMessage(TypedDict):
    """Structure for conversation history messages."""

    role: str
    """'user' or 'assistant'"""

    content: str
    """Message content"""

    timestamp: datetime
    """When the message was sent"""

    user_id: Optional[str]
    """User ID for user messages"""


# =============================================================================
# STATE UTILITY FUNCTIONS
# =============================================================================


def create_initial_state(
    user_message: str,
    user_id: str,
    channel_id: str,
    timestamp: Optional[datetime] = None,
) -> BotState:
    """
    Create an initial state object with default values.

    Args:
        user_message: The Discord message content
        user_id: Discord user ID
        channel_id: Discord channel ID
        timestamp: Message timestamp (defaults to now)

    Returns:
        BotState with all required fields initialized
    """
    if timestamp is None:
        timestamp = datetime.now()

    return BotState(
        # Input data
        user_message=user_message,
        user_id=user_id,
        channel_id=channel_id,
        timestamp=timestamp,
        # Context data (to be filled by workflow)
        personality="",
        user_profile={},
        conversation_history=[],
        rag_context="",
        # LangGraph state (to be filled by chatbot)
        messages=[],
        # Response generation (to be filled by response generator)
        final_response="",
        # Metadata
        execution_time=0.0,
        model_calls=0,
        workflow_path=[],
        debug_info={},
        extracted_artifacts=[],
    )


# Tool results are now handled directly by LangGraph ToolNode
# No need for manual state management


def log_workflow_step(state: BotState, node_name: str) -> None:
    """
    Log that a workflow node was executed.

    Args:
        state: The bot state to modify
        node_name: Name of the workflow node
    """
    state["workflow_path"].append(node_name)


def add_debug_info(state: BotState, key: str, value: Any) -> None:
    """
    Add debug information to the state.

    Args:
        state: The bot state to modify
        key: Debug info key
        value: Debug info value
    """
    state["debug_info"][key] = value


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
        f"💬 Response: {state['final_response'][:100]}{'...' if len(state['final_response']) > 100 else ''}",
        f"⏱️  Execution: {state['execution_time']:.2f}s, {state['model_calls']} LLM calls",
        f"🛤️  Path: {' → '.join(state['workflow_path'])}",
    ]

    return "\n".join(lines)
