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
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

from .state import BotState, format_state_summary
from .message_generator import message_generator_node
from .learn_user_context_node import learn_user_context_node
from ..config import settings
from ..tools import get_all_tools
from ..services import UserService
from ..db import get_session_maker
from ..utils.embeddings import generate_embedding
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore

logger = logging.getLogger(__name__)


def get_config_for_thread(
    thread_id: str, discord_client=None, discord_message=None
) -> RunnableConfig:
    """
    Get LangGraph config for thread-based conversation with Discord context.

    Args:
        thread_id: Thread identifier
        discord_client: Discord client instance for tools
        discord_message: Original Discord message for tools

    Returns:
        LangGraph configuration dictionary with Discord context
    """
    config = RunnableConfig(configurable={"thread_id": thread_id})

    # Add Discord context if available
    if discord_client:
        config["configurable"]["discord_client"] = discord_client
    if discord_message:
        config["configurable"]["discord_message"] = discord_message

    return config


async def chatbot_node(state: BotState) -> BotState:
    """
    Main chatbot node.

    - Uses loaded context and conversation history
    - Uses ChatOpenAI with bind_tools
    - Returns messages that LangGraph automatically routes
    """
    logger.info("💼 Analyzing message for tool usage")

    try:
        # Create system prompt template with proper variable placeholders
        system_prompt_template = textwrap.dedent(
            """
            You are a supervisor for a Discord bot with access to tools.
            Use your personality to decide what tools would enhance the interaction.

            PERSONALITY:
            {personality}

            BOT'S INTERACTION STRATEGY FOR THIS USER:
            {user_context}
            Note: This is YOUR learned strategy for how YOU should interact with this specific user -
            the tone YOU should use, things YOU know they like/dislike that YOU can reference.
            These are the bot's adaptive decisions, not the user's stated preferences.

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

        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_prompt_template), ("human", "{user_input}")]
        )

        # Create the chain and invoke with template variables
        chain = prompt_template | llm_with_tools
        response = await chain.ainvoke(
            {
                "personality": settings.personality.prompt,
                "user_context": state.get("user_context", {}),
                "user_input": state.get("user_message", ""),
            }
        )

        current_user_message = HumanMessage(content=state.get("user_message", ""))

        if hasattr(response, "tool_calls") and response.tool_calls:
            tools = [tc.get("name", "unknown") for tc in response.tool_calls]
            logger.info(f"💼 Chose {len(response.tool_calls)} tools: {tools}")
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
        return "learn_context"

    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    else:
        return "learn_context"


async def load_context_node_with_store(
    state: BotState, store: PostgresStore
) -> BotState:
    """
    Load conversation context using PostgresStore with RAG semantic search.
    """
    logger.info("📑 Loading user and conversation context with RAG")

    try:
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")
        user_message = state.get("user_message", "")

        # Load user context from database
        session_maker = get_session_maker()
        user_service = UserService()
        async with session_maker() as session:
            user_context = await user_service.get_user_context_for_bot(session, user_id)

        namespace = ("conversations", f"channel_{channel_id}")

        # Get recent messages (chronological context)
        recent_messages = await store.asearch(
            namespace, limit=settings.memory.recent_messages_limit
        )
        logger.debug(f"📑 Found {len(recent_messages)} recent messages")

        # Generate embedding for current message for semantic search
        context_messages = []
        current_embedding = None

        if user_message and settings.memory.relevant_messages_limit > 0:
            try:
                current_embedding = await generate_embedding(user_message)
                logger.debug("📊 Generated query embedding for semantic search")
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate query embedding: {e}")

        # Get all messages for semantic search if we have a query embedding
        all_messages = []
        if current_embedding:
            try:
                # Get more messages for semantic search (we'll filter by similarity)
                all_messages = await store.asearch(namespace, limit=100)
                logger.debug(
                    f"📑 Retrieved {len(all_messages)} total messages for semantic search"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to retrieve messages for semantic search: {e}"
                )

        # Process recent messages
        recent_keys = set()
        for msg in recent_messages:
            try:
                msg_data = msg.value
                context_messages.append(
                    {
                        "content": msg_data.get("content", ""),
                        "role": msg_data.get("role", "unknown"),
                        "timestamp": msg_data.get("timestamp", ""),
                        "user_id": msg_data.get("user_id", ""),
                        "context_type": "recent",
                    }
                )
                recent_keys.add(msg.key)
            except Exception as e:
                logger.warning(f"⚠️ Error processing recent message: {e}")

        # Find semantically relevant messages
        if current_embedding and all_messages:
            try:
                from ..utils.embeddings import cosine_similarity

                relevant_candidates = []
                for msg in all_messages:
                    if msg.key in recent_keys:
                        continue  # Skip messages already included as recent

                    try:
                        msg_data = msg.value
                        msg_embedding = msg_data.get("embedding")

                        if msg_embedding and len(msg_embedding) == len(
                            current_embedding
                        ):
                            similarity = cosine_similarity(
                                current_embedding, msg_embedding
                            )

                            if similarity >= settings.memory.similarity_threshold:
                                relevant_candidates.append(
                                    {
                                        "content": msg_data.get("content", ""),
                                        "role": msg_data.get("role", "unknown"),
                                        "timestamp": msg_data.get("timestamp", ""),
                                        "user_id": msg_data.get("user_id", ""),
                                        "context_type": "semantic",
                                        "similarity": similarity,
                                    }
                                )
                    except Exception as e:
                        logger.debug(f"Error processing message for similarity: {e}")
                        continue

                # Sort by similarity and take top N
                relevant_candidates.sort(key=lambda x: x["similarity"], reverse=True)
                relevant_messages = relevant_candidates[
                    : settings.memory.relevant_messages_limit
                ]

                # Add to context
                context_messages.extend(relevant_messages)

                logger.info(
                    f"📑 Found {len(relevant_messages)} semantically relevant messages (threshold: {settings.memory.similarity_threshold})"
                )

            except Exception as e:
                logger.warning(f"⚠️ Error in semantic search: {e}")

        # Sort all context messages by timestamp for chronological order
        try:
            context_messages.sort(key=lambda x: x.get("timestamp", ""))
        except Exception as e:
            logger.warning(f"⚠️ Error sorting context messages: {e}")

        # Store context in state
        state["user_context"] = user_context
        state["conversation_context"] = context_messages

        total_recent = len(
            [m for m in context_messages if m.get("context_type") == "recent"]
        )
        total_semantic = len(
            [m for m in context_messages if m.get("context_type") == "semantic"]
        )

        logger.info(
            f"📑 Loaded conversation context: {total_recent} recent + {total_semantic} semantic = {len(context_messages)} total messages"
        )

        return state

    except Exception as e:
        logger.error(f"❌ Error loading RAG context: {e}")
        # Fallback to minimal context
        state["user_context"] = {"user_id": user_id, "response_tone": "neutral"}
        state["conversation_context"] = []
        return state


async def save_conversation_node_with_store(
    state: BotState,
    store: PostgresStore,
) -> BotState:
    """
    Save conversation using PostgresStore with embeddings for RAG.
    """
    logger.info("💾 Persisting conversation to database with embeddings")

    try:
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")
        user_message = state.get("user_message", "")
        final_response = state.get("final_response", "")

        namespace = ["conversations", f"channel_{channel_id}"]
        timestamp = datetime.now(UTC).isoformat()

        if user_message:
            # Generate embedding for user message
            try:
                user_embedding = await generate_embedding(user_message)
                logger.debug(
                    f"📊 Generated embedding for user message ({len(user_embedding)} dims)"
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate user message embedding: {e}")
                user_embedding = None

            await store.aput(
                tuple(namespace),
                f"msg_{timestamp}_user_{user_id}",
                {
                    "role": "user",
                    "content": user_message,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "timestamp": timestamp,
                    "embedding": user_embedding,
                },
            )

        if final_response:
            # Generate embedding for assistant response
            try:
                assistant_embedding = await generate_embedding(final_response)
                logger.debug(
                    f"📊 Generated embedding for assistant response ({len(assistant_embedding)} dims)"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to generate assistant response embedding: {e}"
                )
                assistant_embedding = None

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
                    "embedding": assistant_embedding,
                },
            )

        logger.info("✅ Conversation saved with embeddings")
        return state

    except Exception as e:
        logger.error(f"❌ Error saving conversation with embeddings: {e}")
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
        # Supervisor pattern: chatbot (supervisor) → tools → learn_context → message_generator → save_conversation
        workflow.add_conditional_edges(
            "chatbot",
            should_continue,
            {"tools": "tools", "learn_context": "learn_context"},
        )
        # Tools → Learn context (analyze interaction strategy)
        workflow.add_edge("tools", "learn_context")
    else:
        # No tools: chatbot → learn_context
        workflow.add_edge("chatbot", "learn_context")

    # Learn context → Message generator → Save conversation
    workflow.add_edge("learn_context", "message_generator")
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
    workflow.add_node("learn_context", learn_user_context_node)
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
    config = get_config_for_thread(
        thread_id=thread_id,
        discord_client=discord_client,
        discord_message=discord_message,
    )

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
                "conversation_context": [],
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
            "conversation_context": [],
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
