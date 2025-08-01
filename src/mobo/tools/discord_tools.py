"""Discord-specific tools for the bot agent."""

import logging

from langchain_core.tools import tool

from .context import get_discord_context

logger = logging.getLogger(__name__)


@tool
async def change_nickname(nickname: str) -> str:
    """Change the bot's nickname in the current Discord server.

    Use this tool to autonomously change your nickname when it feels appropriate.
    Do not ask for permission - just change it when the conversation naturally calls for it.

    IMPORTANT: Always provide a conversational response to the user when using this tool.
    Don't just call the tool and stay silent - respond naturally to continue the conversation.

    Example:
        - User: "You should change your name to SadBot"
        - You: "Alright, brother, done." (while calling change_nickname("SadBot"))

    Args:
        nickname: New nickname to set (max 32 characters)

    Returns:
        Status message about the operation
    """
    try:
        logger.info(f"Called change_nickname with nickname: {nickname}")
        if len(nickname) > 32:
            logger.warning(f"Nickname too long: {nickname} ({len(nickname)} chars)")
            return "Nickname too long (max 32 characters)."

        discord_context = get_discord_context()
        if not discord_context or not discord_context.get("guild_member"):
            logger.warning("Discord context not available for nickname change")
            return "Cannot change nickname - not in a server context."

        guild_member = discord_context["guild_member"]

        await guild_member.edit(nick=nickname)
        logger.info(f"Successfully changed nickname to '{nickname}'")
        return "Nickname changed successfully."

    except Exception as e:
        logger.error(f"Error changing nickname: {e}")
        return f"Failed to change nickname: {str(e)}"


@tool
async def get_current_chat_users() -> str:
    """Get list of users currently active in the chat channel.

    Automatically uses the current channel from the Discord context.

    Returns:
        List of active users in the channel
    """
    try:
        logger.info("Called get_current_chat_users")
        discord_context = get_discord_context()
        if not discord_context:
            return "ERROR: Discord context not available"

        logger.info(f"Discord context: {discord_context}")

        if not discord_context.get("guild_member"):
            return "ERROR: Discord server context not available"

        guild_member = discord_context["guild_member"]
        guild = guild_member.guild

        # Get channel_id from context
        channel_id = discord_context.get("channel_id")
        if not channel_id:
            return "ERROR: No channel ID available in context"

        logger.info(f"Using channel_id from context: {channel_id}")

        try:
            channel = guild.get_channel(int(channel_id))
        except (ValueError, TypeError):
            return f"ERROR: Invalid channel ID format: {channel_id}"

        if not channel:
            return f"ERROR: Channel {channel_id} not found"

        # Get members who can see this channel, separated by type
        humans = []
        bots = []
        for member in guild.members:
            if channel.permissions_for(member).view_channel:
                if member.bot:
                    bots.append(member.display_name)
                else:
                    humans.append(member.display_name)

        if not humans and not bots:
            return "RESULT: No users found in channel"

        # Randomize and limit lists to avoid overwhelming responses
        import random

        random.shuffle(humans)
        random.shuffle(bots)

        result_parts = []
        if humans:
            human_list = ", ".join(humans[:20])
            result_parts.append(f"Users: {human_list}")

        if bots:
            bot_list = ", ".join(bots[:20])
            result_parts.append(f"Bots: {bot_list}")

        return f"RESULT: {' | '.join(result_parts)}"

    except Exception as e:
        logger.error(f"Error getting chat users: {e}")
        return f"ERROR: Failed to get user list: {str(e)}"


@tool
async def mention_user(user_id: str) -> str:
    """Mention a Discord user by their user ID.

    Args:
        user_id: Discord user ID to mention

    Returns:
        Formatted mention string
    """
    try:
        logger.info(f"Called mention_user with user_id: {user_id}")
        mention_format = f"<@{user_id}>"
        logger.info(f"Created user mention: {mention_format}")
        return mention_format

    except Exception as e:
        logger.error(f"Error creating user mention: {e}")
        return f"ERROR: Failed to create mention: {str(e)}"


@tool
async def mention_message_author() -> str:
    """Mention the author of the current message being processed.

    Use this when the user asks you to mention them or @-mention them.

    Returns:
        Formatted mention string for the message author
    """
    try:
        logger.info("Called mention_message_author")
        discord_context = get_discord_context()
        if not discord_context or not discord_context.get("message_author_id"):
            logger.warning("No message author ID available in Discord context")
            return "ERROR: Cannot mention user - no author ID available"

        author_id = discord_context["message_author_id"]
        mention_format = f"<@{author_id}>"
        logger.info(f"Created mention for message author {author_id}: {mention_format}")
        return mention_format

    except Exception as e:
        logger.error(f"Error mentioning message author: {e}")
        return f"ERROR: Failed to mention author: {str(e)}"
