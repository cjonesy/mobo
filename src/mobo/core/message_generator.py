"""
Message generator node for the LangGraph workflow.

This node takes tool results and generates the final personality-driven response.
Uses a larger, more creative model focused purely on response generation.
"""

import logging
import textwrap

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from .state import BotState, log_workflow_step
from ..config import get_settings

logger = logging.getLogger(__name__)


async def message_generator_node(
    state: BotState,
) -> BotState:
    """
    Generate final response using tool results and personality.

    This node takes the tool results from the supervisor and crafts
    a natural, personality-driven response for the user.
    """
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
        user_context = state.get("user_context", {})

        settings = get_settings()
        personality = settings.personality.prompt

        system_prompt = textwrap.dedent(
            f"""
            You are generating the final response for a Discord bot. You have access to tool results - use them to craft an engaging, natural response.

            PERSONALITY:
            {personality}

            USER CONTEXT:
            {user_context}

            RESPONSE GUIDELINES:
            - Be true to your personality and respond naturally
            - Use tool results to enhance your response, don't just repeat them
            - For emoji tools: convert emoji names to actual emoji (thumbs_up → 👍, custom emoji → :name: format)
            - Show enthusiasm that matches your personality
            - Be conversational and engaging
            - Don't mention that you're using tools or processing results
            """
        ).strip()

        # Use a larger model for creative response generation
        llm = ChatOpenAI(
            model=settings.response_llm.model,
            temperature=settings.response_llm.temperature,
            api_key=settings.openrouter.api_key,
            base_url=settings.openrouter.base_url,
        )

        # Get current turn messages from workflow
        current_messages = state.get("messages", [])

        # Check if we only have tool messages (indicating ToolNode replaced messages)
        only_tool_messages = current_messages and all(
            getattr(msg, "type", None) == "tool" for msg in current_messages
        )

        # Extract tool results and incorporate them into the system prompt
        tool_results = []
        user_messages = []

        for msg in current_messages:
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "human":
                    user_messages.append(msg)
                elif msg.type == "tool":
                    tool_results.append(f"Tool result: {msg.content}")

        # Enhance system prompt with tool results
        enhanced_system_prompt = system_prompt
        if tool_results:
            tool_context = "\n".join(tool_results)
            enhanced_system_prompt += f"\n\nTOOL RESULTS:\n{tool_context}\n\nUse the tool results above to inform your response."

        # Build messages for response generation
        # When we only have tool results, we need to reconstruct the user message from state
        if only_tool_messages and not user_messages:
            # Reconstruct user message from state
            user_message_content = state.get("user_message", "")
            from langchain_core.messages import HumanMessage

            user_messages = [HumanMessage(content=user_message_content)]

        # Build messages: system prompt + user messages
        # Tool results are embedded in the enhanced system prompt
        messages = [SystemMessage(content=enhanced_system_prompt)] + user_messages

        # Generate final response
        response = await llm.ainvoke(messages)

        # Update messages to include the final response
        state["messages"] = current_messages + [response]

        # Extract and store final response text
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        state["final_response"] = str(content).strip() if content else ""

        # Update metadata
        state["model_calls"] = state.get("model_calls", 0) + 1

        logger.info(f"✅ Message generated ({len(response.content)} chars)")

        return state

    except Exception as e:
        logger.exception(f"❌ Message generation error: {e}")

        return state
