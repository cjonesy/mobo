"""
Message generator node for the LangGraph workflow.

This node takes tool results and generates the final personality-driven response.
Uses a larger, more creative model focused purely on response generation.
"""

import logging
import time
import textwrap

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import BotState, log_workflow_step, add_debug_info
from .prompt_helpers import build_user_context_text
from ..config import get_settings

logger = logging.getLogger(__name__)


async def message_generator_node(
    state: BotState,
    memory_system,  # LangGraph memory system
) -> BotState:
    """
    Generate final response using tool results and personality.

    This node takes the tool results from the supervisor and crafts
    a natural, personality-driven response for the user.
    """
    start_time = time.time()
    log_workflow_step(state, "message_generator")

    try:
        logger.info("🎨 Generating final response with personality model...")

        # Extract artifacts from ToolMessages before they get processed
        messages_in_state = state.get("messages", [])
        artifacts_found = []
        for msg in messages_in_state:
            if (
                hasattr(msg, "tool_call_id")
                and hasattr(msg, "artifact")
                and msg.artifact
            ):
                artifacts_found.append(msg.artifact)

        # Store artifacts in state for Discord handler
        if artifacts_found:
            state["extracted_artifacts"] = artifacts_found
            logger.info(f"🔧 Preserved {len(artifacts_found)} artifacts in state")

        # Use already loaded context from the load_context node
        personality = state["personality"]
        user_profile = state.get("user_profile", {})
        rag_context = state.get("rag_context", "")

        # Build user context text
        profile_text = build_user_context_text(user_profile)

        settings = get_settings()

        system_prompt = textwrap.dedent(
            f"""
            You are generating the final response for a Discord bot. You have access to tool results - use them to craft an engaging, natural response.

            PERSONALITY:
            {personality}

            USER CONTEXT:
            {profile_text}

            RECENT CONVERSATION HISTORY:
            {rag_context}

            RESPONSE GUIDELINES:
            - Be true to your personality and respond naturally
            - Use tool results to enhance your response, don't just repeat them
            - Remember the conversation history and maintain context
            - For emoji tools: convert emoji names to actual emoji (thumbs_up → 👍, custom emoji → :name: format)
            - Keep responses under 2000 characters for Discord
            - Show enthusiasm that matches your personality
            - Be conversational and engaging
            - Don't mention that you're using tools or processing results
            """
        ).strip()

        # Use a larger model for creative response generation
        # Default to same model, but can be overridden with a separate setting
        response_model = getattr(settings, "response_model", settings.chatbot_model)
        response_temp = getattr(
            settings, "response_temperature", settings.chatbot_temperature
        )

        llm = ChatOpenAI(
            model=response_model,
            temperature=response_temp,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

        # Build conversation with original message and tool results
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User message: {state['user_message']}"),
        ]

        # Add tool results as context in a human message instead of raw tool messages
        tool_results = []
        for message in state.get("messages", []):
            if hasattr(message, "tool_call_id") and hasattr(message, "content"):
                # This is a tool result message
                tool_results.append(f"Tool result: {message.content}")

        if tool_results:
            tool_context = "\n".join(tool_results)
            messages.append(
                HumanMessage(
                    content=f"Tool results:\n{tool_context}\n\nNow generate a natural response using this information."
                )
            )

        # Generate final response
        response = await llm.ainvoke(messages)

        # Store final response in state
        state["messages"] = [response]

        # Update metadata
        execution_time = time.time() - start_time
        state["execution_time"] += execution_time
        state["model_calls"] += 1
        add_debug_info(state, "message_generation_time", execution_time)

        logger.info(f"✅ Message generated ({len(response.content)} chars)")
        logger.debug(f"💬 Generated response: {response.content[:100]}...")

        return state

    except Exception as e:
        logger.exception(f"❌ Message generation error: {e}")

        # Fallback - use any existing tool results or empty
        execution_time = time.time() - start_time
        state["execution_time"] += execution_time
        add_debug_info(state, "message_generation_error", str(e))

        return state
