"""
Discord-specific tools for bot functionality.
"""

import logging

import discord
from pydantic_ai import RunContext

from .dependencies import BotDependencies

logger = logging.getLogger(__name__)


async def list_chat_users(
    ctx: RunContext[BotDependencies],
) -> str:
    """
    List all users in the current chat/channel, distinguishing between bots and humans.

    Use this tool when:
    - User asks "who's here?" or "who's in this chat?"
    - User wants to know who's online or available
    - User asks about other members in the channel
    - User wants to see the member list
    - You need to know who's present for context
    - You want to know which users are bots

    Returns:
        Formatted string with list of users in the current chat
    """
    logger.info(f"🔍 Listing users in channel {ctx.deps.channel_id}")

    try:
        if not ctx.deps.discord_client:
            return "Discord client not available - cannot list users"

        # Get the channel
        channel = ctx.deps.discord_client.get_channel(int(ctx.deps.channel_id))
        if not channel:
            return f"Could not find channel with ID {ctx.deps.channel_id}"

        # Handle different channel types
        if isinstance(channel, discord.DMChannel):
            # For DM channels, just show the other user
            other_user = channel.recipient
            if other_user:
                user_name = other_user.display_name
                if other_user.bot:
                    user_name += " (bot)"
                return f"This is a direct message with {user_name}"
            else:
                return "This is a direct message"

        elif isinstance(channel, discord.GroupChannel):
            # For group DMs
            users = []
            for user in channel.recipients:
                user_name = user.display_name
                if user.bot:
                    user_name += " (bot)"
                users.append(user_name)

            if users:
                users_list = "\n".join(f"• {user}" for user in users)
                return f"Group chat members ({len(users)}):\n{users_list}"
            else:
                return "No other users found in this group chat"

        elif isinstance(channel, (discord.TextChannel, discord.Thread)):
            # For guild channels
            if not channel.guild:
                return "Channel is not in a guild"

            # Get all members who can see this channel
            members = []
            for member in channel.guild.members:
                # Check if member can read the channel
                permissions = channel.permissions_for(member)
                if permissions.read_messages:
                    member_name = member.display_name
                    if member.bot:
                        member_name += " (bot)"
                    members.append(member_name)

            if not members:
                return f"No members found in #{channel.name}"

            # Sort by name
            members.sort(key=lambda x: x.lower())

            members_list = "\n".join(f"• {name}" for name in members)

            return f"Members in #{channel.name} ({len(members)} total):\n{members_list}"

        else:
            return f"Unsupported channel type: {type(channel).__name__}"

    except ValueError as e:
        logger.error(f"Invalid channel ID: {e}")
        return f"Invalid channel ID: {ctx.deps.channel_id}"
    except discord.Forbidden:
        logger.error("Bot lacks permissions to view members")
        return "I don't have permission to view members in this channel"
    except discord.HTTPException as e:
        logger.error(f"Discord API error: {e}")
        return f"Discord API error: {str(e)}"
    except Exception as e:
        logger.error(f"Error listing chat users: {e}")
        return f"Failed to list users: {str(e)}"


async def get_channel_topic(
    ctx: RunContext[BotDependencies],
) -> str:
    """
    Get the topic of the current channel.

    Use this tool when:
    - User asks "what's the topic?" or "what's this channel about?"
    - User wants to know the channel description
    - You need context about the channel's purpose
    - User asks about channel information

    Returns:
        The channel topic or appropriate message if no topic exists
    """
    logger.info(f"🔍 Getting topic for channel {ctx.deps.channel_id}")

    try:
        if not ctx.deps.discord_client:
            return "Discord client not available - cannot get channel topic"

        # Get the channel
        channel = ctx.deps.discord_client.get_channel(int(ctx.deps.channel_id))
        if not channel:
            return f"Could not find channel with ID {ctx.deps.channel_id}"

        # Handle different channel types
        if isinstance(channel, discord.TextChannel):
            if channel.topic:
                return f"Topic for #{channel.name}: {channel.topic}"
            else:
                return f"Channel #{channel.name} has no topic set"

        elif isinstance(channel, discord.DMChannel):
            return "Direct messages don't have topics"

        elif isinstance(channel, discord.GroupChannel):
            return "Group chats don't have topics"

        elif isinstance(channel, discord.Thread):
            return "Threads don't have topics"

        else:
            return f"Channel type {type(channel).__name__} doesn't support topics"

    except ValueError as e:
        logger.error(f"Invalid channel ID: {e}")
        return f"Invalid channel ID: {ctx.deps.channel_id}"
    except discord.Forbidden:
        logger.error("Bot lacks permissions to view channel")
        return "I don't have permission to view this channel"
    except discord.HTTPException as e:
        logger.error(f"Discord API error: {e}")
        return f"Discord API error: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting channel topic: {e}")
        return f"Failed to get channel topic: {str(e)}"
