"""
Conversation history search tool for Discord bot.
"""

import logging

from pydantic_ai import RunContext

from .dependencies import BotDependencies

logger = logging.getLogger(__name__)


async def search_conversation_history(
    ctx: RunContext[BotDependencies], query: str
) -> str:
    """
    Search for relevant past conversations using stored embeddings.

    Uses pre-computed embeddings stored in the database and only generates
    an embedding for the search query, making searches much faster and cheaper.

    Use this tool when:
    - Users ask about their name, personal details, or anything they mentioned before
    - Users reference something from a previous conversation ("remember when...", "like I said before...")
    - You need context about the user's interests, preferences, or past topics (e.g. "what did I tell you about...")
    - Users ask "what did I tell you about..." or similar memory-based questions
    - You need to remember something from a previous conversation

    Args:
        query: Search query to find relevant past conversations

    Returns:
        Formatted string with relevant conversation excerpts and context
    """
    try:
        logger.info(f"🔍 search_conversation_history tool called with query: {query}")
        memory = ctx.deps.memory
        user_id = ctx.deps.user_id

        # Search for similar messages in user's conversation history
        similar_messages = await memory.search_similar_messages(
            query_text=query, user_id=user_id, limit=5, similarity_threshold=0.3
        )

        if not similar_messages:
            return f"No relevant past conversations found for query: '{query}'"

        result_parts = [
            f"Found {len(similar_messages)} relevant past conversations for '{query}':\n"
        ]

        for i, msg_info in enumerate(similar_messages, 1):
            content_preview = (
                msg_info.content[:200] + "..."
                if len(msg_info.content) > 200
                else msg_info.content
            )

            result_parts.append(
                f"{i}. ({msg_info.created_at.strftime('%Y-%m-%d %H:%M')}): {content_preview}"
            )

        return "\n".join(result_parts)

    except Exception as e:
        logger.error(f"Error searching conversation history: {e}")
        return f"Error searching conversation history: {str(e)}"
