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
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    BaseMessage,
    AIMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig

from .state import (
    BotState,
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
    logger.info("💼 Analyzing message for tool usage")

    try:

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
            - Consider what tools would best express your personality in this situation
            - Be creative! Feel free to use tools in unexpected ways!

            You are choosing tools for the response.

            The message generator will create the final response with your personality.
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
            tool_names = [tool.name for tool in tools]
            logger.info(
                f"💼 Found {len(tools)} tools available", extra={"tools": tool_names}
            )
            llm_with_tools = llm.bind_tools(tools)
        else:
            logger.info("💼 No tools available")
            llm_with_tools = llm

        current_user_message = HumanMessage(content=state["user_message"])

        conversation = [SystemMessage(content=system_prompt), current_user_message]

        response = await llm_with_tools.ainvoke(conversation)

        # Log tool call decision
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_names = [
                tool_call.get("name", "unknown") for tool_call in response.tool_calls
            ]
            logger.info(
                f"💼 Chose {len(response.tool_calls)} tools",
                extra={"tools": tool_names},
            )
            for i, tool_call in enumerate(response.tool_calls):
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                logger.debug(f"💼 Tool {i+1} - {tool_name} with args: {tool_args}")
        else:
            logger.info("💼 No tools needed, proceeding to response")

        return {
            **state,
            "messages": [current_user_message, response],
            "model_calls": state.get("model_calls", 0) + 1,
        }

    except Exception as e:
        logger.exception(f"❌ Chatbot node error: {e}")
        return {
            **state,
            "messages": state.get("messages", [])
            + [HumanMessage(content=state["user_message"])],
        }


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
        return "tools"
    else:
        return "message_generator"


async def load_context_node_with_store(
    state: BotState, store: PostgresStore
) -> BotState:
    """
    Load conversation context using PostgresStore.
    """
    logger.info("📑 Loading user and conversation context")

    try:
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")

        session_maker = get_session_maker()
        user_service = UserService()
        async with session_maker() as session:
            user_context = await user_service.get_user_context_for_bot(session, user_id)

        namespace = ("conversations", f"channel_{channel_id}")
        recent_messages = await store.asearch(namespace, limit=10)  # type: ignore

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

        conversation_context.sort(key=lambda x: x["timestamp"])

        logger.info(f"📑 Loaded {len(conversation_context)} messages from context")

        state["user_context"] = user_context
        return state

    except Exception as e:
        logger.error(f"Error loading context: {e}")
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
    logger.info("💾 Persisting conversation to database")

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

        return state

    except Exception as e:
        logger.error(f"❌ Error saving conversation: {e}")
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
    logger.info("⛓️ Creating bot workflow")
    workflow = StateGraph(BotState)

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
    return compiled_workflow


async def create_workflow_for_message(
    database_url: str,
    user_message: str,
    user_id: str,
    channel_id: str,
    discord_client=None,
    discord_message=None,
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
    logger.info("✉️ Creating workflow for message")
    with PostgresStore.from_conn_string(database_url) as store:
        async with AsyncPostgresSaver.from_conn_string(database_url) as checkpointer:
            workflow = await create_bot_workflow(checkpointer, store)

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
    discord_client=None,
    discord_message=None,
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
    logger.info("📨 Executing workflow")
    thread_id = f"discord_channel_{channel_id}"
    config = get_config_for_thread(thread_id)

    if discord_client or discord_message:
        config["configurable"]["discord_client"] = discord_client
        config["configurable"]["discord_message"] = discord_message

    current_state: BotState
    try:
        existing_state = await workflow.aget_state(config)
        if existing_state.values:
            current_state = cast(BotState, existing_state.values.copy())
            current_state.update(
                {
                    "user_message": user_message,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "timestamp": datetime.now(UTC),
                }
            )
        else:
            current_state = {
                "user_message": user_message,
                "user_id": user_id,
                "channel_id": channel_id,
                "timestamp": datetime.now(UTC),
                "user_context": {},
                "messages": [],
                "final_response": None,
                "model_calls": 0,
                "extracted_artifacts": [],
            }
    except Exception as e:
        logger.debug(f"❌ Could not get existing state: {e}, creating new")
        current_state = {
            "user_message": user_message,
            "user_id": user_id,
            "channel_id": channel_id,
            "timestamp": datetime.now(UTC),
            "user_context": {},
            "messages": [],
            "final_response": None,
            "model_calls": 0,
            "extracted_artifacts": [],
        }

    try:
        final_state = await workflow.ainvoke(current_state, config=config)
        return cast(BotState, final_state)

    except Exception as e:
        logger.exception(f"❌ Workflow execution failed: {e}")

        error_state = current_state.copy()
        error_state["final_response"] = None

        return cast(BotState, error_state)


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
