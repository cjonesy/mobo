"""Discord-specific tools for the bot agent."""

import logging
from typing import Optional

import discord
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
async def get_current_chat_users(channel_id: Optional[str] = None) -> str:
    """Get list of users currently active in the chat channel.

    Args:
        channel_id: Discord channel ID (optional, will use current channel if not provided)

    Returns:
        List of active users in the channel
    """
    try:
        discord_context = get_discord_context()
        if not discord_context or not discord_context.get("guild_member"):
            return "ERROR: Discord server context not available"

        guild_member = discord_context["guild_member"]
        guild = guild_member.guild

        # Use provided channel_id or get from context
        channel_id_to_use = channel_id or discord_context.get("channel_id")
        if not channel_id_to_use:
            return "ERROR: No channel ID available"

        channel = guild.get_channel(int(channel_id_to_use))
        if not channel:
            return f"ERROR: Channel {channel_id_to_use} not found"

        # Get members who can see this channel
        visible_members = []
        for member in guild.members:
            if channel.permissions_for(member).view_channel and not member.bot:
                visible_members.append(member.display_name)

        if not visible_members:
            return "RESULT: No users found in channel"

        # Limit to first 20 to avoid overwhelming responses
        if len(visible_members) > 20:
            visible_members = visible_members[:20]
            user_list = ", ".join(visible_members)
            return (
                f"RESULT: {user_list} (showing first 20 of {len(guild.members)} total)"
            )
        else:
            user_list = ", ".join(visible_members)
            return f"RESULT: {user_list}"

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
        mention_format = f"<@{user_id}>"
        logger.info(f"Created user mention: {mention_format}")
        return mention_format

    except Exception as e:
        logger.error(f"Error creating user mention: {e}")
        return f"ERROR: Failed to create mention: {str(e)}"
