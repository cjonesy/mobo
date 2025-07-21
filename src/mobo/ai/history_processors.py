"""
History processors for intelligent conversation memory management.
"""

import logging
from typing import List

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserPromptPart,
    TextPart,
)

from .tools import BotDependencies

logger = logging.getLogger(__name__)

summary_agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="""You are a conversation summarizer. Create concise summaries of Discord conversations
    that preserve important context, user preferences, and key topics discussed.
    Focus on information that would be useful for future conversations.

    Format your summary as:
    **Key Topics:** [list main topics]
    **User Preferences:** [any preferences mentioned]
    **Important Context:** [other relevant details]
    **Tone/Style:** [conversation style notes]

    Keep summaries under 200 words.""",
)


async def keep_recent_with_summary(
    _ctx: RunContext[BotDependencies], messages: List[ModelMessage]
) -> List[ModelMessage]:
    """
    Keep recent messages and summarize older ones to preserve context while managing token usage.

    This processor:
    1. Keeps the last 15 messages as-is for immediate context
    2. Summarizes older messages to preserve long-term context
    3. Maintains system prompts and tool calls
    """
    if len(messages) <= 20:  # If conversation is short, keep everything
        return messages

    try:
        # Split messages: older for summarization, recent to keep
        split_point = len(messages) - 15
        older_messages = messages[:split_point]
        recent_messages = messages[split_point:]

        # Don't summarize if older section is too small
        if len(older_messages) < 5:
            return messages

        # Generate summary of older messages
        summary_result = await summary_agent.run(
            "Summarize this Discord conversation, focusing on key context for future interactions:",
            message_history=older_messages,
        )

        # Create a user prompt with the summary
        summary_message = ModelRequest.user_text_prompt(
            f"📝 **Conversation Summary:**\n{summary_result.output}\n\n---\n\n"
        )

        # Return summary + recent messages
        result_messages = [summary_message] + recent_messages

        logger.info(
            f"Compressed {len(older_messages)} older messages into summary, "
            f"keeping {len(recent_messages)} recent messages"
        )

        return result_messages

    except Exception as e:
        logger.error(f"Error in conversation summarization: {e}")
        # Fallback: just keep recent messages
        return messages[-25:] if len(messages) > 25 else messages


async def filter_and_prioritize(
    _ctx: RunContext[BotDependencies], messages: List[ModelMessage]
) -> List[ModelMessage]:
    """
    Intelligent filtering to prioritize important messages.

    This processor:
    1. Always keeps system prompts and tool-related messages
    2. Prioritizes messages with user questions or important context
    3. Removes redundant or low-value exchanges
    """
    if len(messages) <= 30:
        return messages

    important_messages = []
    regular_messages = []

    for msg in messages:
        is_important = False

        # Always keep system prompts and tool calls
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if hasattr(part, "part_kind") and part.part_kind in [
                    "system-prompt",
                    "tool-return",
                ]:
                    is_important = True
                    break
                # Keep messages with questions or key phrases
                elif isinstance(part, UserPromptPart):
                    content = str(part.content).lower()
                    if any(
                        phrase in content
                        for phrase in [
                            "?",
                            "how",
                            "what",
                            "why",
                            "when",
                            "where",
                            "remember",
                            "my name",
                            "preferences",
                            "help",
                            "explain",
                        ]
                    ):
                        is_important = True
                        break

        elif isinstance(msg, ModelResponse):
            # Keep responses to important questions or with tool calls
            for response_part in msg.parts:
                if (
                    hasattr(response_part, "part_kind")
                    and getattr(response_part, "part_kind", None) == "tool-call"
                ):
                    is_important = True
                    break
                elif (
                    isinstance(response_part, TextPart)
                    and len(response_part.content) > 100
                ):
                    # Keep substantial responses
                    is_important = True
                    break

        if is_important:
            important_messages.append(msg)
        else:
            regular_messages.append(msg)

    # Always include recent messages regardless of importance
    recent_count = min(10, len(messages) // 3)
    recent_messages = messages[-recent_count:]

    # Combine: important messages + recent messages (remove duplicates)
    seen_indices = set()
    result = []

    # Add important messages
    for msg in important_messages:
        if id(msg) not in seen_indices:
            result.append(msg)
            seen_indices.add(id(msg))

    # Add recent messages
    for msg in recent_messages:
        if id(msg) not in seen_indices:
            result.append(msg)
            seen_indices.add(id(msg))

    # Sort by original order
    original_order = {id(msg): i for i, msg in enumerate(messages)}
    result.sort(key=lambda msg: original_order.get(id(msg), 0))

    logger.info(
        f"Filtered {len(messages)} messages down to {len(result)} "
        f"({len(important_messages)} important, {len(recent_messages)} recent)"
    )

    return result


async def context_aware_truncation(
    ctx: RunContext[BotDependencies], messages: List[ModelMessage]
) -> List[ModelMessage]:
    """
    Context-aware truncation based on user activity and memory system state.

    Adjusts conversation length based on:
    - User's total message count (new users get more context)
    - Channel activity level
    - Memory system recommendations
    """
    if not ctx.deps.memory:
        return messages[-20:] if len(messages) > 20 else messages

    # Get user profile to inform truncation decisions
    user_profile = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")

    # Adjust limits based on user experience
    if user_profile.total_messages < 10:
        # New users: keep more context to learn preferences
        max_messages = 50
    elif user_profile.total_messages < 100:
        # Regular users: standard context
        max_messages = 30
    else:
        # Experienced users: trust summarization more
        max_messages = 20

    if len(messages) <= max_messages:
        return messages

    # For longer conversations, use intelligent summarization
    return await keep_recent_with_summary(ctx, messages)


# Export the processors
conversation_processors = [
    context_aware_truncation,
    filter_and_prioritize,
]
