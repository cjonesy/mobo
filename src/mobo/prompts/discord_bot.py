"""Discord bot prompt templates."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Optional


def create_discord_bot_prompt(
    personality_prompt: str,
    user_profile: Optional[dict] = None,
    rag_context: Optional[str] = None,
) -> ChatPromptTemplate:
    """
    Create a chat prompt template for the Discord bot.

    Args:
        personality_prompt: The bot's personality/system prompt
        user_profile: Optional user profile information
        rag_context: Optional RAG context from conversation history

    Returns:
        ChatPromptTemplate configured for the Discord bot
    """
    system_parts = [personality_prompt]

    # Add user profile context if available
    if user_profile:
        tone = user_profile.get("tone", "neutral")
        likes = user_profile.get("likes", [])
        dislikes = user_profile.get("dislikes", [])

        profile_parts = [f"Tone: {tone}"]
        if likes:
            profile_parts.append(f"Likes: {', '.join(likes[:3])}")
        if dislikes:
            profile_parts.append(f"Dislikes: {', '.join(dislikes[:3])}")

        system_parts.append(f"\nUser Profile - {', '.join(profile_parts)}")

    # Add RAG context if available
    if rag_context:
        system_parts.append(f"\nRecent conversation context:\n{rag_context}")

    system_message = "".join(system_parts)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    return prompt


def create_simple_discord_bot_prompt() -> ChatPromptTemplate:
    """
    Create a simple chat prompt template for the Discord bot.

    Returns:
        ChatPromptTemplate configured for the Discord bot
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    return prompt
