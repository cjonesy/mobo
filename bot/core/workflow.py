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
import time
import textwrap

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import (
    BotState,
    log_workflow_step,
    add_debug_info,
    create_initial_state,
    format_state_summary,
)
from .response_extractor import response_extractor_node, format_response_summary
from .message_generator import message_generator_node
from .prompt_utils import load_personality_and_user_context
from ..config import Settings, get_settings
from ..tools import get_all_tools
from ..memory.langgraph_memory import get_config_for_thread

logger = logging.getLogger(__name__)


async def chatbot_node(
    state: BotState,
    memory_system,
) -> BotState:
    """
    Main chatbot node.

    - Loads context from LangGraph store
    - Uses ChatOpenAI with bind_tools
    - Returns messages that LangGraph automatically routes
    """
    start_time = time.time()
    log_workflow_step(state, "chatbot")

    try:
        logger.info(f"🤖 Processing message: {state['user_message'][:100]}...")

        # Load bot personality and user context
        personality, profile_text = await load_personality_and_user_context(
            memory_system, state["user_id"]
        )

        settings = get_settings()

        system_prompt = textwrap.dedent(
            f"""
            You are a supervisor for a Discord bot with access to tools.
            Use your personality to decide what tools would enhance the interaction.

            PERSONALITY:
            {personality}

            USER CONTEXT:
            {profile_text}

            GUIDELINES:
            - Stay true to your personality when choosing tools
            - Use tools when they would make the response more engaging or helpful in-character
            - Don't use tools just because you can - only when they add genuine value for your personality
            - Consider what tools would best express your personality in this situation

            You are choosing tools for the response. The message generator will create the final response with your personality.
        """
        ).strip()

        llm = ChatOpenAI(
            model=settings.chatbot_model,
            temperature=settings.chatbot_temperature,
            api_key=settings.openrouter_api_key.get_secret_value(),
            base_url=settings.openrouter_base_url,
        )

        tools = get_all_tools()
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["user_message"]),
        ]

        # Get response from LLM
        response = await llm_with_tools.ainvoke(messages)

        # Store in state for LangGraph routing
        state["messages"] = [response]

        # Update metadata
        execution_time = time.time() - start_time
        state["execution_time"] += execution_time
        state["model_calls"] += 1
        add_debug_info(state, "chatbot_execution_time", execution_time)

        logger.info("✅ Chatbot processing completed")
        return state

    except Exception as e:
        logger.exception(f"❌ Chatbot error: {e}")
        # Clear messages on error
        state["messages"] = []
        execution_time = time.time() - start_time
        state["execution_time"] += execution_time
        add_debug_info(state, "chatbot_error", str(e))
        return state


def should_continue(state: BotState) -> str:
    """
    Standard LangGraph conditional edge using LangChain message patterns.

    Checks if the last message has tool calls using LangChain's standard pattern.
    This replaces our custom supervisor logic with LangGraph built-ins.
    """
    messages = state.get("messages", [])
    if not messages:
        return "message_generator"

    last_message = messages[-1]

    # Use LangChain's standard tool_calls attribute
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"🔧 {len(last_message.tool_calls)} tool calls detected")
        for tool_call in last_message.tool_calls:
            logger.info(f"🔧 Tool call: {tool_call}")
        return "tools"
    else:
        logger.info("⏭️ No tool calls, proceeding to message generation")
        return "message_generator"


def create_bot_workflow(
    settings: Settings,
    memory_system,
) -> StateGraph:
    """
    Create the main bot workflow using modern LangGraph patterns.

    Args:
        settings: Bot configuration
        memory_system: LangGraph memory system with checkpointing

    Returns:
        Compiled LangGraph workflow with automatic persistence
    """
    logger.info("🏗️ Creating bot workflow...")

    # Create nodes with injected dependencies
    async def chatbot_with_memory(state: BotState) -> BotState:
        return await chatbot_node(state, memory_system)

    workflow = StateGraph(BotState)

    # Add nodes - supervisor -> tools -> message generator -> response extractor
    workflow.add_node("chatbot", chatbot_with_memory)
    workflow.add_node("response_extractor", response_extractor_node)

    # Create message generator with injected dependencies
    async def message_generator_with_memory(state: BotState) -> BotState:
        return await message_generator_node(state, memory_system)

    workflow.add_node("message_generator", message_generator_with_memory)

    # Add tool-related nodes - using all registered tools
    tools = get_all_tools()
    has_tools = bool(tools)

    if has_tools:
        tools_node = ToolNode(tools)
        workflow.add_node("tools", tools_node)

    workflow.set_entry_point("chatbot")

    if has_tools:
        # Supervisor pattern: chatbot (supervisor) → tools → message_generator → response_extractor
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

    # Message generator → Response extractor
    workflow.add_edge("message_generator", "response_extractor")

    # Response extractor → End
    workflow.add_edge("response_extractor", END)

    # Compile the workflow with LangGraph checkpointing and store
    compiled_workflow = workflow.compile(
        checkpointer=memory_system.checkpointer,
        store=memory_system.store,
    )

    logger.info("✅ Bot workflow created successfully")

    if has_tools:
        logger.info(
            "🛤️ Workflow path: chatbot (supervisor) → tools → message_generator → response_extractor → END"
        )
        logger.info(f"🛠️ {len(tools)} tools available")
    else:
        logger.info(
            "🛤️ Workflow path: chatbot → message_generator → response_extractor → END"
        )
        logger.info("⚠️ No tools available")

    logger.info("🚀 Using standard LangGraph patterns with built-in persistence")

    return compiled_workflow


# =============================================================================
# WORKFLOW EXECUTION HELPERS
# =============================================================================


async def execute_workflow(
    workflow: StateGraph, user_message: str, user_id: str, channel_id: str
) -> BotState:
    """
    Execute the workflow with thread-based conversation using LangGraph.

    Args:
        workflow: Compiled LangGraph workflow with checkpointing
        user_message: The Discord message content
        user_id: Discord user ID
        channel_id: Discord channel ID

    Returns:
        Final state after workflow execution
    """
    # Create initial state
    initial_state = create_initial_state(
        user_message=user_message, user_id=user_id, channel_id=channel_id
    )

    # Get thread ID for this channel
    thread_id = f"discord_channel_{channel_id}"
    config = get_config_for_thread(thread_id)

    logger.info(
        f"🚀 Executing workflow for message: {user_message[:50]}... (thread: {thread_id})"
    )
    start_time = time.time()

    try:
        # Execute the workflow with thread-based checkpointing
        final_state = await workflow.ainvoke(initial_state, config=config)

        # Update total execution time
        total_time = time.time() - start_time
        final_state["execution_time"] = total_time

        logger.info(f"✅ Workflow completed in {total_time:.2f}s")
        logger.info(f"🛤️ Path taken: {' → '.join(final_state['workflow_path'])}")

        return final_state

    except Exception as e:
        logger.exception(f"❌ Workflow execution failed: {e}")

        # Return error state
        error_state = initial_state.copy()
        error_state["final_response"] = None
        error_state["execution_time"] = time.time() - start_time
        add_debug_info(error_state, "workflow_error", str(e))

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
        "personality",
        "final_response",
    ]

    for field in required_fields:
        if not state.get(field):
            errors.append(f"Missing required field: {field}")

    # Check response length
    response = state.get("final_response", "")
    if len(response) > 2000:
        errors.append(f"Response too long: {len(response)} > 2000 characters")

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
    lines = [
        "🔄 Workflow Execution Summary",
        "=" * 40,
        format_state_summary(state),
        "",
        format_response_summary(state),
        "",
        f"⏱️ Total Execution Time: {state['execution_time']:.2f}s",
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
