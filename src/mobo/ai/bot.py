"""
PydanticAI-based Discord bot implementation.

This module provides the core bot functionality using PydanticAI's Agent class
with intelligent conversation memory and tool integration.
"""

import logging
from typing import Optional

import discord
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest

from .memory_manager import MemoryManager
from .tools import BotDependencies, get_discord_tools
from ..utils.config import get_config

logger = logging.getLogger(__name__)


def create_discord_agent() -> Agent[BotDependencies, str]:
    """Create and configure the PydanticAI agent for Discord with memory."""
    config = get_config()

    system_prompt = config.get_resolved_system_prompt_sync()

    agent = Agent(
        model=config.openai_model,
        system_prompt=system_prompt,
        tools=get_discord_tools(),
        deps_type=BotDependencies,
    )

    return agent


async def process_discord_message(
    agent: Agent[BotDependencies, str],
    memory: MemoryManager,
    user_message: str,
    user_id: str,
    channel_id: str,
    username: str = "",
    discord_client: Optional[discord.Client] = None,
    guild_id: Optional[str] = None,
) -> str:
    """Process a Discord message through the PydanticAI agent with memory."""
    try:
        # Get user profile to personalize response
        user_profile = await memory.get_or_create_user(user_id, username)
        logger.debug(
            f"Retrieved user profile for {username} ({user_id}): style={user_profile.conversation_style}, topics={user_profile.topics_of_interest}"
        )

        conversation_id = await memory.start_conversation(user_id, channel_id)

        conversation_history = await memory.get_conversation_history(
            user_id, channel_id, limit=20
        )

        # Create user profile context to influence response style
        profile_context_parts = []

        if (
            user_profile.conversation_style
            and user_profile.conversation_style != "friendly"
        ):
            profile_context_parts.append(
                f"Respond to user as if you are {user_profile.conversation_style}"
            )

        if user_profile.topics_of_interest:
            topics_str = ", ".join(user_profile.topics_of_interest)
            profile_context_parts.append(f"User is interested in: {topics_str}")

        # Always add style management reminder with current style info
        profile_context_parts.append(
            f"Current conversation style: '{user_profile.conversation_style}'. Monitor this user's communication patterns and proactively update their conversation_style if their tone, formality, or approach suggests a different style would be more appropriate"
        )

        # Inject user profile context
        profile_context = "\n".join(profile_context_parts)
        user_message_with_context = (
            f"[User Profile Context: {profile_context}]\n\n{user_message}"
        )
        logger.debug(f"Added profile context: {profile_context}")

        deps = BotDependencies(
            memory=memory,
            user_id=user_id,
            channel_id=channel_id,
            discord_client=discord_client,
            guild_id=guild_id,
        )

        result = await agent.run(
            user_message_with_context, deps=deps, message_history=conversation_history
        )

        # Store the original message (without context) in memory
        user_msg = ModelRequest.user_text_prompt(user_message)
        await memory.add_message(conversation_id, user_msg, "user")

        if result.new_messages():
            for new_msg in result.new_messages():
                await memory.add_message(conversation_id, new_msg, "assistant")

        return result.data

    except Exception as e:
        logger.error(f"Error processing Discord message: {e}")
        return "I encountered an error processing your message."
