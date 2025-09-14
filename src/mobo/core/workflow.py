"""
LangGraph workflow definition for the Discord bot.

This file defines the main workflow that orchestrates the supervisor pattern:
1. Load context (user profile, conversation history)
2. Supervisor analysis (decide what tools to use)
3. Tool execution (if needed)
4. Response generation
5. Save conversation to memory
"""

import logging
import textwrap
from typing import cast
from datetime import datetime, UTC

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from .state import (
    BotState,
    log_workflow_step,
    format_state_summary,
)
from .message_generator import message_generator_node
from ..config import get_settings
from ..tools import get_all_tools
from ..services import UserService
from ..db import get_session_maker
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore

logger = logging.getLogger(__name__)


def get_config_for_thread(thread_id: str) -> RunnableConfig:
    """
    Get LangGraph config for thread-based conversation.

    Args:
        thread_id: Thread identifier

    Returns:
        LangGraph configuration dictionary
    """
    return RunnableConfig(configurable={"thread_id": thread_id})


async def chatbot_node(state: BotState) -> BotState:
    """
    Main chatbot node.

    - Uses loaded context and conversation history
    - Uses ChatOpenAI with bind_tools
    - Returns messages that LangGraph automatically routes
    """
    log_workflow_step(state, "chatbot")

    try:
        logger.info(f"🤖 Processing message: {state['user_message'][:100]}...")

        user_context = state.get("user_context", {})

        settings = get_settings()
        personality = settings.personality.prompt

        system_prompt = textwrap.dedent(
            f"""
            You are a supervisor for a Discord bot with access to tools.
            Use your personality to decide what tools would enhance the interaction.

            PERSONALITY:
            {personality}

            USER CONTEXT:
            {user_context}

            GUIDELINES:
            - Stay true to your personality when choosing tools
            - Use tools when they would make the response more engaging or helpful in-character
            - Don't use tools just because you can - only when they add genuine value for your personality
            - Consider what tools would best express your personality in this situation

            You are choosing tools for the response. The message generator will create the final response with your personality.
        """
        ).strip()

        llm = ChatOpenAI(
            model=settings.supervisor_llm.model,
            temperature=settings.supervisor_llm.temperature,
            api_key=settings.openrouter.api_key,
            base_url=settings.openrouter.base_url,
        )

        tools = get_all_tools()
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        # Build messages for this turn (just system + user message)
        # LangGraph will manage conversation history via checkpointer
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["user_message"]),
        ]

        response = await llm_with_tools.ainvoke(messages)

        # Store current turn's messages for LangGraph routing
        # Include the user message and AI response for proper tool call flow
        state["messages"] = messages + [response]

        # Update metadata
        state["model_calls"] = state.get("model_calls", 0) + 1

        logger.info("✅ Chatbot processing completed")
        return state

    except Exception as e:
        logger.exception(f"❌ Chatbot error: {e}")
        return state


def should_continue(state: BotState) -> str:
    """
    Standard LangGraph conditional edge using LangChain message patterns.

    Checks if the last message has tool calls.
    """
    messages = state.get("messages", [])

    if not messages:
        return "message_generator"

    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"🔧 {len(last_message.tool_calls)} tool calls detected")
        return "tools"
    else:
        return "message_generator"


async def load_context_node_with_store(
    state: BotState, store: PostgresStore
) -> BotState:
    """
    Load conversation context using PostgresStore.
    """
    try:
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")

        # Get user profile
        session_maker = get_session_maker()
        user_service = UserService()
        async with session_maker() as session:
            user_context = await user_service.get_user_context_for_bot(session, user_id)

        # Get recent conversation context using PostgresStore directly
        namespace = ("conversations", f"channel_{channel_id}")
        recent_messages = await store.asearch(namespace, limit=10)  # type: ignore

        # Format conversation context
        conversation_context = []
        for item in recent_messages:
            msg = item.value
            conversation_context.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp", ""),
                }
            )

        # Sort by timestamp (most recent last)
        conversation_context.sort(key=lambda x: x["timestamp"])

        # Update state
        state["user_context"] = user_context

        logger.info(
            f"✅ Loaded context: {len(conversation_context)} messages, user: {user_id}"
        )
        return state

    except Exception as e:
        logger.error(f"❌ Error loading context with PostgresStore: {e}")
        # Fallback to minimal context
        state["user_context"] = {"user_id": user_id, "response_tone": "neutral"}
        return state


async def save_conversation_node_with_store(
    state: BotState,
    store: PostgresStore,
) -> BotState:
    """
    Save conversation using PostgresStore.
    """
    try:
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")
        user_message = state.get("user_message", "")
        final_response = state.get("final_response", "")

        namespace = ["conversations", f"channel_{channel_id}"]
        timestamp = datetime.now(UTC).isoformat()

        if user_message:
            await store.aput(
                tuple(namespace),
                f"msg_{timestamp}_user_{user_id}",
                {
                    "role": "user",
                    "content": user_message,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "timestamp": timestamp,
                },
            )

        if final_response:
            await store.aput(
                tuple(namespace),
                f"msg_{timestamp}_assistant_{user_id}",
                {
                    "role": "assistant",
                    "content": final_response,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "timestamp": timestamp,
                    "model_used": "gpt-4",
                },
            )

        logger.info(
            f"✅ Saved conversation to PostgresStore: {len(user_message or '')} + {len(final_response or '')} chars"
        )
        return state

    except Exception as e:
        logger.error(f"❌ Error saving conversation to PostgresStore: {e}")
        return state


async def create_bot_workflow(checkpointer, store) -> CompiledStateGraph:
    """
    Create the main bot workflow with provided checkpointer and store

    Args:
        checkpointer: AsyncPostgresSaver instance for persistence
        store: PostgresStore instance for conversation storage

    Returns:
        Compiled LangGraph workflow with persistence
    """
    logger.info("🏗️ Creating bot workflow...")

    workflow = StateGraph(BotState)

    # Add tool-related nodes
    tools = get_all_tools()
    has_tools = bool(tools)

    if has_tools:
        tools_node = ToolNode(tools)
        workflow.add_node("tools", tools_node)

    workflow.set_entry_point("load_context")

    # Context loading → Chatbot
    workflow.add_edge("load_context", "chatbot")

    if has_tools:
        # Supervisor pattern: chatbot (supervisor) → tools → message_generator → save_conversation
        workflow.add_conditional_edges(
            "chatbot",
            should_continue,
            {"tools": "tools", "message_generator": "message_generator"},
        )
        # Tools → Message generator (personality response)
        workflow.add_edge("tools", "message_generator")
    else:
        # No tools: chatbot → message_generator
        workflow.add_edge("chatbot", "message_generator")

    # Message generator → Save conversation
    workflow.add_edge("message_generator", "save_conversation")

    # Save conversation → End
    workflow.add_edge("save_conversation", END)

    # Use provided checkpointer and store
    # Create wrapper functions for store access
    async def load_context_with_store(state: BotState) -> BotState:
        return await load_context_node_with_store(state, store)  # type: ignore

    async def save_conversation_with_store(state: BotState) -> BotState:
        return await save_conversation_node_with_store(state, store)  # type: ignore

    workflow.add_node("load_context", load_context_with_store)
    workflow.add_node("chatbot", chatbot_node)
    workflow.add_node("message_generator", message_generator_node)
    workflow.add_node("save_conversation", save_conversation_with_store)

    # Compile workflow with provided checkpointer
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Bot workflow created successfully")

    if has_tools:
        logger.info(
            "🛤️ Workflow path: load_context → chatbot (supervisor) → tools → message_generator → save_conversation → END"
        )
        logger.info(f"🛠️ {len(tools)} tools available")
    else:
        logger.info(
            "🛤️ Workflow path: load_context → chatbot → message_generator → save_conversation → END"
        )
        logger.info("⚠️ No tools available")

    logger.info("🚀 Using standard LangGraph patterns with built-in persistence")

    return compiled_workflow


async def create_workflow_for_message(
    database_url: str,
    user_message: str,
    user_id: str,
    channel_id: str,
    discord_client = None,
    discord_message = None,
) -> BotState:
    """
    Create a workflow for a single message and execute it.

    This follows the LangGraph recommended pattern of creating workflow per request
    with proper connection management.

    Args:
        database_url: PostgreSQL connection string
        user_message: The Discord message content
        user_id: Discord user ID
        channel_id: Discord channel ID
        discord_client: Discord client instance for tools
        discord_message: Original Discord message for tools

    Returns:
        Final state after workflow execution
    """
    # Create fresh checkpointer and store for this message
    # Note: PostgresStore is a regular context manager, AsyncPostgresSaver is async
    with PostgresStore.from_conn_string(database_url) as store:
        async with AsyncPostgresSaver.from_conn_string(database_url) as checkpointer:
            # Create workflow with these instances
            workflow = await create_bot_workflow(checkpointer, store)

            # Execute workflow
            return await execute_workflow(
                workflow=workflow,
                user_message=user_message,
                user_id=user_id,
                channel_id=channel_id,
                discord_client=discord_client,
                discord_message=discord_message,
            )


async def execute_workflow(
    workflow: CompiledStateGraph,
    user_message: str,
    user_id: str,
    channel_id: str,
    discord_client = None,
    discord_message = None,
) -> BotState:
    """
    Execute the workflow with thread-based conversation using LangGraph.

    Args:
        workflow: Compiled LangGraph workflow with checkpointing
        user_message: The Discord message content
        user_id: Discord user ID
        channel_id: Discord channel ID
        discord_client: Discord client instance for tools
        discord_message: Original Discord message for tools

    Returns:
        Final state after workflow execution
    """
    initial_state: BotState = {
        "user_message": user_message,
        "user_id": user_id,
        "channel_id": channel_id,
        "timestamp": datetime.now(UTC),
        "user_context": {},
        "messages": [],
        "final_response": None,
        "model_calls": 0,
        "workflow_path": [],
        "extracted_artifacts": [],
    }

    thread_id = f"discord_channel_{channel_id}"
    config = get_config_for_thread(thread_id)

    # Add Discord context to config for tools
    if discord_client or discord_message:
        config["configurable"]["discord_client"] = discord_client
        config["configurable"]["discord_message"] = discord_message

    logger.info(
        f"🚀 Executing workflow for message: {user_message[:50]}... (thread: {thread_id})"
    )

    try:
        final_state = await workflow.ainvoke(initial_state, config=config)

        # Update total execution time
        logger.info("✅ Workflow completed")
        logger.info(f"🛤️ Path taken: {' → '.join(final_state['workflow_path'])}")

        return cast(BotState, final_state)

    except Exception as e:
        logger.exception(f"❌ Workflow execution failed: {e}")

        error_state = initial_state.copy()
        error_state["final_response"] = None

        return error_state


def validate_workflow_state(state: BotState) -> list[str]:
    """
    Validate that the workflow state is consistent and complete.

    Args:
        state: Bot state to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required fields
    required_fields = [
        "user_message",
        "user_id",
        "channel_id",
        "timestamp",
        "final_response",
    ]

    for field in required_fields:
        if not state.get(field):
            errors.append(f"Missing required field: {field}")

    # Check execution path
    if not state.get("workflow_path"):
        errors.append("No workflow path recorded")

    return errors


def format_workflow_summary(state: BotState) -> str:
    """
    Create a comprehensive summary of workflow execution.

    Args:
        state: Final bot state

    Returns:
        Multi-line summary string
    """
    response = state.get("final_response") or ""
    lines = [
        "🔄 Workflow Execution Summary",
        "=" * 40,
        format_state_summary(state),
        "",
        "💬 Final Response:",
        f"   📝 Length: {len(response)} characters",
        f"   💭 Response: {response[:100]}{'...' if len(response) > 100 else ''}",
        "",
        f"🔄 Model Calls: {state['model_calls']}",
        f"🛤️ Workflow Path: {' → '.join(state['workflow_path'])}",
    ]

    # Add validation results
    validation_errors = validate_workflow_state(state)
    if validation_errors:
        lines.extend(
            [
                "",
                "⚠️ Validation Issues:",
                *[f"   - {error}" for error in validation_errors],
            ]
        )
    else:
        lines.append("✅ State validation passed")

    return "\n".join(lines)
