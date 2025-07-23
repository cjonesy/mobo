"""
Discord-specific tools for bot functionality.
"""

import logging

import discord
from pydantic_ai import RunContext

from .dependencies import BotDependencies

logger = logging.getLogger(__name__)


async def mention_user(
    ctx: RunContext[BotDependencies],
    username_or_id: str,
) -> str:
    """
    Create a proper Discord mention that will actually notify the user.

    CRITICAL: Never write @username directly - it won't work! You MUST use this tool.

    Use this tool when:
    - User says "mention me", "can you mention me", "@-mention me", etc.
      → Use the Current User info from the message context
    - You want to mention any specific user
    - Instead of writing @someone in your response

    Args:
        username_or_id: Username (like "cjonesy") or Discord user ID to mention

    Returns:
        Working Discord mention format like <@123456789> that notifies the user
    """
    logger.info(f"🔗 mention_user tool called for: {username_or_id}")

    try:
        if not ctx.deps.discord_client:
            return f"@{username_or_id}"  # Fallback format

        # Get the channel
        channel = ctx.deps.discord_client.get_channel(int(ctx.deps.channel_id))
        if not channel:
            return f"@{username_or_id}"

        # Only handle guild channels since this bot doesn't DM
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return f"@{username_or_id}"

        if not channel.guild:
            return f"@{username_or_id}"

        # Try to find the user
        target_member = None

        # First, check if it's already a user ID (all digits)
        if username_or_id.isdigit():
            target_member = channel.guild.get_member(int(username_or_id))
        else:
            # Search by username or display name
            for member in channel.guild.members:
                if (
                    member.name.lower() == username_or_id.lower()
                    or member.display_name.lower() == username_or_id.lower()
                ):
                    target_member = member
                    break

        if target_member:
            return f"<@{target_member.id}>"
        else:
            return f"@{username_or_id}"  # Fallback if user not found

    except Exception as e:
        logger.error(f"Error getting mention format for {username_or_id}: {e}")
        return f"@{username_or_id}"


async def list_chat_users(
    ctx: RunContext[BotDependencies],
) -> str:
    """
    List all users who can see this channel with comprehensive information.

    This tool provides detailed information about channel members including:
    - Display names and user IDs for mentioning
    - Whether each user is a bot or human
    - Ready-to-use Discord mention formats (use these DIRECTLY in your responses)

    IMPORTANT FOR MENTIONS: When you need to @-mention someone in your response,
    copy the exact mention format from this tool's output (like <@123456789>).
    Never use plain text like "@username" as it won't notify the user.

    Use this tool when:
    - User asks "who's here?" or "who's in this chat?"
    - User wants to know who's online or available
    - User asks about other members in the channel
    - User wants to see the member list
    - You need to know who you can mention
    - You need to mention someone and want their proper Discord mention format
    - You want to look up users by name or user ID
    - You want to know which users are bots

    Returns:
        Formatted string with comprehensive user information and ready-to-use mention formats
    """
    logger.info(f"🔍 Listing users in channel {ctx.deps.channel_id}")

    try:
        if not ctx.deps.discord_client:
            return "Discord client not available - cannot list users"

        # Get the channel
        channel = ctx.deps.discord_client.get_channel(int(ctx.deps.channel_id))
        if not channel:
            return f"Could not find channel with ID {ctx.deps.channel_id}"

        # Only handle guild channels since this bot doesn't DM
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return (
                f"This bot only works in guild channels, not {type(channel).__name__}"
            )

        if not channel.guild:
            return "Channel is not in a guild"

        # Get all members who can see this channel
        members_info = []
        total_guild_members = len(channel.guild.members)

        for member in channel.guild.members:
            # Check if member can read the channel
            permissions = channel.permissions_for(member)
            if permissions.read_messages:
                user_id = str(member.id)
                global_username = member.name
                server_display_name = member.display_name
                mention_format = f"<@{user_id}>"

                members_info.append(
                    {
                        "global_username": global_username,
                        "server_display_name": server_display_name,
                        "user_id": user_id,
                        "mention_format": mention_format,
                        "is_bot": member.bot,
                    }
                )

        if not members_info:
            return f"No members found in #{channel.name} (checked {total_guild_members} guild members)"

        # Sort by global username
        members_info.sort(key=lambda x: x["global_username"].lower())

        # Create structured output
        result_parts = [
            f"Channel: #{channel.name}",
            f"Total members: {len(members_info)} (from {total_guild_members} guild members)",
            "",
        ]

        # Group by type
        humans = [m for m in members_info if not m["is_bot"]]
        bots = [m for m in members_info if m["is_bot"]]

        if humans:
            result_parts.append("HUMANS:")
            for member in humans:
                result_parts.append(
                    f"  global_username: {member['global_username']}, "
                    f"server_display_name: {member['server_display_name']}, "
                    f"user_id: {member['user_id']}, "
                    f"mention: {member['mention_format']}"
                )
            result_parts.append("")

        if bots:
            result_parts.append("BOTS:")
            for member in bots:
                result_parts.append(
                    f"  global_username: {member['global_username']}, "
                    f"server_display_name: {member['server_display_name']}, "
                    f"user_id: {member['user_id']}, "
                    f"mention: {member['mention_format']}"
                )

        return "\n".join(result_parts)

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
