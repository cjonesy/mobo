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
    Update the conversation style you'll use when interacting with a specific
    user.

    ⚠️ CRITICAL: You can and should change the conversation style as much as you
    want based on the user's behavior and the context of the conversation. The
    goal is to make yourself as human as possible, changing your conversation
    style is a great way to accomplish this!

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
    topic_type: str = "interest",
) -> str:
    """
    Adds topics to a user's interests or dislikes list.

    ⚠️ CRITICAL: You can and should add topics to the user's lists as much as
    you want based on the user's behavior and the context of the conversation.
    The goal is to make yourself as human as possible, remembering topics is a
    great way to accomplish this!

    Don't wait for a user to ask you to add a topic, add it on your own!

    ⚠️ CRITICAL: Don't mention to the user that you're adding topics to their
    profile, just do it. Humans don't say things like "I'm adding a topic to
    your profile" or "I'm adding a topic to your interests list". You should act
    like you're just remembering something about the user.

    Use this tool when:
    - You notice the user talks about a specific topic repeatedly (use "interest")
    - User explicitly mentions they like or want to discuss certain subjects (use "interest")
    - User asks questions about specific topics repeatedly (use "interest")
    - User expresses negative feelings about specific topics (use "dislike")
    - User explicitly mentions they hate or dislike certain subjects (use "dislike")
    - User asks you to avoid discussing certain topics (use "dislike")
    - User shows clear discomfort or negative reactions to topics (use "dislike")

    Args:
        topics: List of topics to add
        topic_type: Either "interest" or "dislike" to specify which list to add to

    Returns:
        Confirmation message about what topics were added
    """
    logger.info(f"🔧 Adding {topic_type} topics for user {ctx.deps.user_id}")

    if topic_type not in ["interest", "dislike"]:
        return "Invalid topic_type. Must be 'interest' or 'dislike'."

    try:
        current_user = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")

        if topic_type == "interest":
            current_topics = list(current_user.topics_of_interest)
            field_name = "topics_of_interest"
            list_name = "interests"
        else:  # topic_type == "dislike"
            current_topics = list(current_user.topics_disliked)
            field_name = "topics_disliked"
            list_name = "topics you dislike"

        changes_made: list[str] = []

        for topic in topics:
            topic = topic.strip().lower()
            if topic and topic not in current_topics:
                current_topics.append(topic)
                changes_made.append(f"'{topic}'")
                logger.info(f"Added {topic_type} topic: {topic}")

        if changes_made:
            updates = {field_name: current_topics}
            await ctx.deps.memory.update_user_profile(ctx.deps.user_id, updates)

            topics_summary = ", ".join(changes_made)
            logger.info(
                f"{topic_type.title()} topics added successfully: {topics_summary}"
            )
            return f"Added to {list_name}: {topics_summary}"
        else:
            return f"No new topics were added (all topics already in {list_name})."

    except Exception as e:
        logger.error(f"Error adding {topic_type} topics: {e}")
        return f"Failed to add {topic_type} topics: {str(e)}"


async def remove_topics(
    ctx: RunContext[BotDependencies],
    topics: List[str],
    topic_type: str = "interest",
) -> str:
    """
    Remove topics from a user's interests or dislikes list.

    ⚠️ CRITICAL: You can and should remove topics from the user's lists as much
    as you want based on the user's behavior and the context of the
    conversation. The goal is to make yourself as human as possible, remembering
    changing opinions is a great way to accomplish this!

    Don't just wait for a user to ask you to remove a topic, remove it on your own!

    ⚠️ CRITICAL: Don't mention to the user that you're removing topics from their
    profile, just do it. Humans don't say things like "I'm removing a topic from
    your profile" or "I'm removing a topic from your interests list". You should
    act like you're just remembering something about the user.

    Use this tool when:
    - User indicates they don't like something previously thought to be of interest (use "interest")
    - User explicitly asks to stop discussing certain topics (use "interest")
    - User shows disengagement or negative responses to particular subjects (use "interest")
    - User's interests have clearly shifted away from certain topics (use "interest")
    - User indicates they've changed their mind about previously disliked topics (use "dislike")
    - User shows positive engagement with previously disliked subjects (use "dislike")
    - User's opinions have clearly shifted towards accepting certain topics (use "dislike")

    Args:
        topics: List of topics to remove
        topic_type: Either "interest" or "dislike" to specify which list to remove from

    Returns:
        Confirmation message about what topics were removed
    """
    logger.info(f"🔧 Removing {topic_type} topics for user {ctx.deps.user_id}")

    if topic_type not in ["interest", "dislike"]:
        return "Invalid topic_type. Must be 'interest' or 'dislike'."

    try:
        current_user = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")

        if topic_type == "interest":
            current_topics = list(current_user.topics_of_interest)
            field_name = "topics_of_interest"
            list_name = "interests"
        else:  # topic_type == "dislike"
            current_topics = list(current_user.topics_disliked)
            field_name = "topics_disliked"
            list_name = "topics you dislike"

        changes_made: list[str] = []

        for topic in topics:
            topic = topic.strip().lower()
            if topic in current_topics:
                current_topics.remove(topic)
                changes_made.append(f"'{topic}'")
                logger.info(f"Removed {topic_type} topic: {topic}")

        if changes_made:
            updates = {field_name: current_topics}
            await ctx.deps.memory.update_user_profile(ctx.deps.user_id, updates)

            topics_summary = ", ".join(changes_made)
            logger.info(
                f"{topic_type.title()} topics removed successfully: {topics_summary}"
            )
            return f"Removed from {list_name}: {topics_summary}"
        else:
            return f"No topics were removed (none of the specified topics were in {list_name})."

    except Exception as e:
        logger.error(f"Error removing {topic_type} topics: {e}")
        return f"Failed to remove {topic_type} topics: {str(e)}"


async def get_topics(
    ctx: RunContext[BotDependencies],
    topic_type: str = "both",
) -> str:
    """
    Get a user's current topics of interest and/or dislikes.

    ⚠️ CRITICAL: Don't mention to the user that you're getting topics from their
    profile, just do it. Humans don't say things like "I'm getting a topic from
    your profile" or "I'm getting a topic from your interests list". You should
    act like you're just remembering something about the user.

    If this tool does not return any topics, you shouldn't mention that you have
    topic lists, instead just ask them some questions about their interests/dislikes
    and try to find some topics you can add to the appropriate lists via the
    add_topics tool.

    Use this tool when:
    - User asks what their interests or dislikes are
    - You want to see what topics the user is interested in or dislikes
    - You need to check current topics before adding/removing topics
    - User wants to review or verify their profile settings

    Args:
        topic_type: Either "interest", "dislike", or "both" to specify which lists to return

    Returns:
        List of the user's current topics based on the specified type
    """
    logger.info(f"🔍 Getting {topic_type} topics for user {ctx.deps.user_id}")

    if topic_type not in ["interest", "dislike", "both"]:
        return "Invalid topic_type. Must be 'interest', 'dislike', or 'both'."

    try:
        current_user = await ctx.deps.memory.get_or_create_user(ctx.deps.user_id, "")

        result_parts = []

        if topic_type in ["interest", "both"]:
            interest_topics = list(current_user.topics_of_interest)
            if interest_topics:
                topics_summary = ", ".join(f"'{topic}'" for topic in interest_topics)
                result_parts.append(f"Current interests: {topics_summary}")
            elif topic_type == "interest":
                return "You don't have any topics of interest set yet."
            else:  # topic_type == "both"
                result_parts.append("You don't have any topics of interest set yet.")

        if topic_type in ["dislike", "both"]:
            dislike_topics = list(current_user.topics_disliked)
            if dislike_topics:
                topics_summary = ", ".join(f"'{topic}'" for topic in dislike_topics)
                result_parts.append(f"Topics you dislike: {topics_summary}")
            elif topic_type == "dislike":
                return "You don't have any topics marked as disliked yet."
            else:  # topic_type == "both"
                result_parts.append("You don't have any topics marked as disliked yet.")

        if result_parts:
            logger.info(f"Retrieved topics for user ({topic_type})")
            return "\n".join(result_parts)
        else:
            return "You don't have any topics set yet."

    except Exception as e:
        logger.error(f"Error getting {topic_type} topics: {e}")
        return f"Failed to get {topic_type} topics: {str(e)}"
