"""
Message generator node for the LangGraph workflow.

This node takes tool results and generates the final personality-driven response.
Uses LangChain's native message handling patterns for cleaner integration.
"""

import logging
import textwrap

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import List

from .state import BotState
from ..config import settings

logger = logging.getLogger(__name__)


async def message_generator_node(
    state: BotState,
) -> BotState:
    """
    Generate final response using tool results and personality.

    This node takes the tool results from the supervisor and crafts
    a natural, personality-driven response for the user.
    """
    logger.info("✒️ Creating personality-driven response")

    try:
        # Create system prompt template with proper variable placeholders
        system_prompt_template = textwrap.dedent(
            """
            You are generating the final response for a Discord bot.

            PERSONALITY:
            {personality}

            USER CONTEXT:
            {user_context}

            RESPONSE GUIDELINES:
            - Be true to your personality and respond naturally
            - Show enthusiasm that matches your personality
            - Be conversational and engaging
            - Don't mention that you're using tools or processing results
            """
        ).strip()

        # Extract artifacts from messages
        state["extracted_artifacts"] = [
            msg.artifact
            for msg in state.get("messages", [])
            if (
                hasattr(msg, "tool_call_id")
                and hasattr(msg, "artifact")
                and msg.artifact
            )
        ]

        llm = ChatOpenAI(
            model=settings.response_llm.model,
            temperature=settings.response_llm.temperature,
            api_key=settings.openrouter.api_key,
            base_url=settings.openrouter.base_url,
        )

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt_template),
                MessagesPlaceholder("conversation_history", optional=True),
                ("human", "{user_input}"),
            ]
        )

        # Filter and organize messages using LangChain patterns
        conversation_history: List[BaseMessage] = []
        tool_context_parts = []

        current_messages = state.get("messages", [])

        # Separate tool results from conversation messages
        for msg in current_messages:
            if hasattr(msg, "type"):
                if msg.type == "tool":
                    # Extract tool results for context
                    tool_context_parts.append(f"Tool result: {msg.content}")
                elif msg.type in ["human", "ai", "assistant"]:
                    conversation_history.append(msg)

        # Create enhanced system prompt template that includes tool results as a variable
        enhanced_system_prompt_template = (
            system_prompt_template
            + textwrap.dedent(
                """

            TOOL RESULTS:
            {tool_results}

            Use the tool results above to inform your response.
            """
            ).strip()
        )

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", enhanced_system_prompt_template),
                MessagesPlaceholder("conversation_history", optional=True),
                ("human", "{user_input}"),
            ]
        )

        # Create the chain and invoke with structured data
        chain = prompt_template | llm
        response = await chain.ainvoke(
            {
                "personality": settings.personality.prompt,
                "user_context": state.get("user_context", {}),
                "conversation_history": conversation_history,
                "user_input": state.get("user_message", ""),
                "tool_results": "\n".join(tool_context_parts),
            }
        )

        # Update messages to include the final response
        state["messages"] = current_messages + [response]

        # Extract and store final response text
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        state["final_response"] = str(content).strip() if content else ""

        final_resp = state.get("final_response", "")
        logger.info(
            f"📝 Final response: {final_resp[:50] if final_resp else 'None'}..."
        )

        state["model_calls"] = state.get("model_calls", 0) + 1

        return state

    except Exception as e:
        logger.exception(f"❌ Message generation error: {e}")
        return state
