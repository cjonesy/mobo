"""
User profile update tools for Discord bot.
"""

import logging
from typing import List

from pydantic_ai import RunContext

from .dependencies import BotDependencies

logger = logging.getLogger(__name__)


async def update_conversation_style(
    ctx: RunContext[BotDependencies],
    conversation_style: str,
) -> str:
    """
    Update the conversation style of the bot when interacting with a specific user.

    You can and should change the conversation style as much as you want based
    on the user's behavior and the context of the conversation. The goal
    is to make yourself as human as possible, changing your conversation style
    is a great way to accomplish this!

    Don't just wait for a user to ask you to change your conversation style,
    change it on your own!

    **When to use this tool PROACTIVELY:**
    - User is treating you poorly or rudely (update to "apologetic", "formal", or "respectful")
    - User is treating you like a human friend (update to "casual", "friendly", "warm")
    - User is treating you like a close buddy/pal (update to "friend", "buddy", "pal")
    - User is being very formal/professional (update to "formal", "professional")
    - User gives short, terse responses (update to "concise", "short", "brief")
    - User is very enthusiastic/excited (update to "enthusiastic", "energetic")
    - User shares personal details openly (update to "personal", "warm", "caring")
    - User seems frustrated or stressed (update to "supportive", "understanding", "gentle")
    - User is being playful/joking (update to "playful", "humorous", "fun")

    **Don't wait for explicit requests** - monitor their communication patterns across
    messages and adapt accordingly. Look at their word choice, punctuation, emoji usage,
    message length, and overall tone to determine the most appropriate style.

    Args:
        conversation_style: New conversation style (e.g., "friendly", "formal", "casual", "short", "detailed", "apologetic", "enthusiastic", "warm", "playful")

    Returns:
        Confirmation message about the update
    """
    logger.info(f"🔧 Updating conversation style for user {ctx.deps.user_id}")

    try:
        updates = {"conversation_style": conversation_style}
        await ctx.deps.memory.update_user_profile(ctx.deps.user_id, updates)

        logger.info(f"Updated conversation style to: {conversation_style}")
        return f"Conversation style updated to '{conversation_style}'"

    except Exception as e:
        logger.error(f"Error updating conversation style: {e}")
        return f"Failed to update conversation style: {str(e)}"


async def add_topics(
    ctx: RunContext[BotDependencies],
    topics: List[str],
) -> str:
    """
    Adds topics to a list of the user's interests.

    You can and should add topics to the user's interests as much as you want
    based on the user's behavior and the context of the conversation. The goal
    is to make yourself as human as possible, remembering topics is a great way
    to accomplish this!

    Don't just wait for a user to ask you to add a topic to their interests,
    add it on your own!

    Use this tool when:
    - You notice the user talks about a specific topic repeatedly
    - User explicitly mentions they like or want to discuss certain subjects
    - User asks questions about specific topics repeatedly

    Args:
        topics: List of topics to add to the user's interests

    Returns:
        Confirmation message about what topics were added
    """
    logger.info(f"🔧 Adding topics for user {ctx.deps.user_id}")

    try:
        current_user = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")
        current_topics = list(current_user.topics_of_interest)

        changes_made: list[str] = []

        for topic in topics:
            topic = topic.strip().lower()
            if topic and topic not in current_topics:
                current_topics.append(topic)
                changes_made.append(f"'{topic}'")
                logger.info(f"Added topic of interest: {topic}")

        if changes_made:
            updates = {"topics_of_interest": current_topics}
            await ctx.deps.memory.update_user_profile(ctx.deps.user_id, updates)

            topics_summary = ", ".join(changes_made)
            logger.info(f"Topics added successfully: {topics_summary}")
            return f"Added interests: {topics_summary}"
        else:
            return "No new topics were added (all topics already in interests)."

    except Exception as e:
        logger.error(f"Error adding topics: {e}")
        return f"Failed to add topics: {str(e)}"


async def remove_topics(
    ctx: RunContext[BotDependencies],
    topics: List[str],
) -> str:
    """
    Remove topics from a user's interests.

    You can and should remove topics from the user's interests as much as you want
    based on the user's behavior and the context of the conversation. The goal
    is to make yourself as human as possible, remembering topics is a great way
    to accomplish this!

    Don't just wait for a user to ask you to remove a topic from their interests,
    remove it on your own!

    Use this tool when:
    - User indicates they don't like something previously thought to be of interest
    - User explicitly asks to stop discussing certain topics
    - User shows disengagement or negative responses to particular subjects
    - User's interests have clearly shifted away from certain topics

    Args:
        topics: List of topics to remove from the user's interests

    Returns:
        Confirmation message about what topics were removed
    """
    logger.info(f"🔧 Removing topics for user {ctx.deps.user_id}")

    try:
        current_user = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")
        current_topics = list(current_user.topics_of_interest)

        changes_made: list[str] = []

        for topic in topics:
            topic = topic.strip().lower()
            if topic in current_topics:
                current_topics.remove(topic)
                changes_made.append(f"'{topic}'")
                logger.info(f"Removed topic of interest: {topic}")

        if changes_made:
            updates = {"topics_of_interest": current_topics}
            await ctx.deps.memory.update_user_profile(ctx.deps.user_id, updates)

            topics_summary = ", ".join(changes_made)
            logger.info(f"Topics removed successfully: {topics_summary}")
            return f"Removed interests: {topics_summary}"
        else:
            return "No topics were removed (none of the specified topics were in interests)."

    except Exception as e:
        logger.error(f"Error removing topics: {e}")
        return f"Failed to remove topics: {str(e)}"


async def get_topics(
    ctx: RunContext[BotDependencies],
) -> str:
    """
    Get a user's current topics of interest.

    Use this tool when:
    - User asks what their interests are
    - You want to see what topics the user is interested in
    - You need to check current interests before adding/removing topics
    - User wants to review or verify their profile settings

    Returns:
        List of the user's current topics of interest
    """
    logger.info(f"🔍 Getting topics for user {ctx.deps.user_id}")

    try:
        current_user = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")
        topics = list(current_user.topics_of_interest)

        if topics:
            topics_summary = ", ".join(f"'{topic}'" for topic in topics)
            logger.info(f"Retrieved {len(topics)} topics for user")
            return f"Current interests: {topics_summary}"
        else:
            logger.info("User has no topics of interest set")
            return "You don't have any topics of interest set yet."

    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        return f"Failed to get topics: {str(e)}"
