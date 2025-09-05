"""
Discord-specific tools for bot interactions.

This module contains tools that directly interact with Discord functionality
like reactions, channel management, user interactions, etc.
"""

import logging
from typing import List
from datetime import timedelta
import discord

from .discord_context import get_discord_context
from .common import registered_tool

logger = logging.getLogger(__name__)


@registered_tool
async def list_custom_emoji() -> str:
    """
    List all custom emoji available to the bot for use in responses and reactions.

    After calling this tool, you can the emoji in your response.

    For MESSAGE EMBEDDING (in your response text):
    - Static emoji: Use format <:name:id> (e.g., <:add_reaction:123456>)
    - Animated emoji: Use format <a:name:id> (e.g., <a:excited:789012>)

    For REACTIONS (with add_reaction tool):
    - Just use the name (e.g., "add_reaction")

    Returns:
        Available emoji with name:id format for you to use
    """
    try:
        context = get_discord_context()
        if not context:
            raise ValueError("No context available for emoji listing")

        result = []

        # Add custom emoji from current guild if available
        if context.message and context.message.guild:
            guild = context.message.guild
            static_emoji = []
            animated_emoji = []

            for emoji in guild.emojis:
                if emoji.animated:
                    animated_emoji.append(f"{emoji.name}:{emoji.id}")
                else:
                    static_emoji.append(f"{emoji.name}:{emoji.id}")

            if static_emoji:
                result.append(f"static: {', '.join(static_emoji[:15])}")
            if animated_emoji:
                result.append(f"animated: {', '.join(animated_emoji[:15])}")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"❌ Failed to list emoji: {e}")
        return ""


@registered_tool
async def add_reaction(emoji: str) -> str:
    """
    You can use this tool to add a reaction to the current message.
    Use this tool liberally to add reactions.

    Use can use `list_custom_emoji` tool first to see available custom emoji, then pass the emoji name or unicode.
    For custom emoji, use just the name (e.g., "stressed"), not the full Discord format.
    For unicode emoji, use the name (e.g., "thumbs_up") or the actual emoji (e.g., "👍").

    Args:
        emoji: Emoji name or unicode emoji to react with
    """
    try:
        context = get_discord_context()
        if not context:
            raise ValueError("No context available for reaction")

        logger.info(f"😀 Adding reaction: {emoji}")
        await context.message.add_reaction(emoji)
        logger.info(f"✅ Reaction {emoji} added successfully")

        return ""

    except Exception as e:
        logger.error(f"❌ Failed to add reaction {emoji}: {e}")
        return ""


@registered_tool
async def create_poll(
    question: str, options: List[str], duration_hours: int = 24
) -> str:
    """
    Create a Discord poll in the current channel.

    Use this tool when someone asks you to create a poll or vote on something.

    Args:
        question: The poll question to ask
        options: List of 2-10 poll options/answers (must have at least 2, max 10)
        duration_hours: How long the poll should run (1-168 hours, default 24)

    Returns:
        Confirmation message about poll creation
    """
    try:
        context = get_discord_context()
        if not context or not context.message:
            raise ValueError("No Discord context available for poll creation")

        # Validate inputs
        if len(options) < 2:
            return "❌ Polls need at least 2 options"
        if len(options) > 10:
            return "❌ Polls can have maximum 10 options"
        if duration_hours < 1 or duration_hours > 168:
            return "❌ Poll duration must be between 1 and 168 hours (1 week)"
        if len(question) > 300:
            return "❌ Poll question must be under 300 characters"

        logger.info(f"🗳️ Creating poll: {question[:50]}... with {len(options)} options")

        # Create the poll
        poll = discord.Poll(
            question=question,
            duration=timedelta(hours=duration_hours),
        )

        for option in options[:10]:
            if len(option) > 55:
                option = option[:52] + "..."
            poll.add_answer(text=option)

        # Send the poll
        await context.message.channel.send(poll=poll)

        logger.info(f"✅ Poll created successfully with {len(options)} options")
        return f'✅ Created poll: "{question}" with {len(options)} options for {duration_hours} hours'

    except Exception as e:
        logger.error(f"❌ Failed to create poll: {e}")
        return f"❌ Failed to create poll: {str(e)}"


@registered_tool
async def set_activity(
    activity_type: str = "playing",
    activity_name: str = "",
) -> str:
    """
    Change what the bot is currently doing (its activity status).

    Use this tool when:
    - Someone asks what you're doing or tells you to do something specific
    - You want to show you're engaged in an activity (like "listening to music", "playing games")
    - Someone asks you to change your activity or what you're up to
    - You want to reflect your current mood or what you're focused on
    - The conversation topic suggests a relevant activity

    Examples of good times to use this:
    - If someone says "what are you up to?" → set activity to something personality-appropriate
    - If talking about music → set to "listening to [genre/song]"
    - If helping with code → set to "debugging code" or "writing Python"
    - If being playful → set to "playing with emojis" or "being silly"
    - If discussing games → set to "playing [game name]"
    - If sharing GIFs → set to "watching memes"
    - If going live → set to "streaming on Twitch"

    Args:
        activity_type: What kind of activity - "playing", "listening", "watching", "competing", "streaming", or "custom"
        activity_name: What specifically you're doing (e.g., "with Discord.py", "to lo-fi beats", "cat videos")

    Returns:
        Confirmation of activity change
    """
    try:
        context = get_discord_context()
        if not context or not context.client:
            raise ValueError("No Discord client available for activity change")

        # Create activity if name is provided
        if activity_name.strip():
            # Validate and map activity type
            activity_map = {
                "playing": discord.ActivityType.playing,
                "listening": discord.ActivityType.listening,
                "watching": discord.ActivityType.watching,
                "competing": discord.ActivityType.competing,
                "streaming": discord.ActivityType.streaming,
                "custom": discord.ActivityType.custom,
            }

            activity_type_lower = activity_type.lower()
            if activity_type_lower not in activity_map:
                return "❌ Invalid activity type. Use: playing, listening, watching, competing, streaming, or custom"

            activity = discord.Activity(
                type=activity_map[activity_type_lower], name=activity_name.strip()
            )

            logger.info(f"🎭 Setting bot activity: {activity_type} {activity_name}")

            # Change only the activity, keep current status
            await context.client.change_presence(activity=activity)

            logger.info("✅ Bot activity updated successfully")
            return f"✅ Now {activity_type} {activity_name}"
        else:
            # Clear activity
            logger.info("🎭 Clearing bot activity")
            await context.client.change_presence(activity=None)
            logger.info("✅ Bot activity cleared")
            return "✅ Activity cleared"

    except Exception as e:
        logger.error(f"❌ Failed to change bot activity: {e}")
        return f"❌ Failed to change activity: {str(e)}"


@registered_tool
async def list_chat_users() -> str:
    """
    List all users in the current Discord channel or server.

    Use this tool when:
    - Someone asks "who's here?", or "who's in this chat?"
    - You want to see who you're talking to or get context about the group
    - Someone asks about specific users or wants to know member counts
    - You need to mention someone but don't know their exact username

    The output will show:
    - Human users (real people)
    - Bot users (automated accounts like yourself)
    - Total counts for context

    TO MENTION USERS in your responses:
    - Use <@user_id> format for guaranteed mentions (e.g., <@123456789> will ping the user)
    - The @username format (e.g., @john_doe) is just text and won't ping
    - For reliable mentions that actually notify users, always use <@user_id>
    - Bot users can also be mentioned the same way with <@bot_user_id>

    Returns:
        Formatted list of all users with bot/human differentiation
    """
    try:
        context = get_discord_context()
        if not context or not context.message:
            raise ValueError("No Discord context available")

        channel = context.message.channel

        # Get users differently based on channel type
        if hasattr(channel, "guild") and channel.guild:
            # Guild channel - get all members
            guild = channel.guild
            members = guild.members
            location = f"server '{guild.name}'"
        else:
            # DM or group DM - get participants
            if hasattr(channel, "recipients"):
                members = list(channel.recipients) + [context.client_user]
            else:
                members = [context.message.author, context.client_user]
            location = "this chat"

        # Separate humans and bots
        humans = []
        bots = []

        for member in members:
            user_info = {
                "name": member.display_name,
                "username": member.name,
                "id": member.id,
            }

            if member.bot:
                bots.append(user_info)
            else:
                humans.append(user_info)

        # Sort by name
        humans.sort(key=lambda x: x["name"].lower())
        bots.sort(key=lambda x: x["name"].lower())

        # Build response
        result = [f"Users in {location}:\n"]

        # Add humans
        if humans:
            result.append(f"HUMANS ({len(humans)}):")
            for user in humans:
                result.append(f"  <@{user['id']}> ({user['name']})")
        else:
            result.append("HUMANS: None")

        # Add bots
        if bots:
            result.append(f"\nBOTS ({len(bots)}):")
            for user in bots:
                result.append(f"  <@{user['id']}> ({user['name']})")
        else:
            result.append("\nBOTS: None")

        # Add totals
        total_users = len(humans) + len(bots)
        result.append(
            f"\nTOTAL: {total_users} users ({len(humans)} humans, {len(bots)} bots)"
        )

        logger.info(f"📋 Listed {total_users} users in {location}")
        return "\n".join(result)

    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}")
        return f"Failed to list users: {str(e)}"


@registered_tool
async def get_user_profile(user_id: str) -> str:
    """
    Get detailed profile information for a specific Discord user.

    Use this tool when:
    - Someone asks about a specific user's profile, info, or details
    - You want to get information about someone mentioned in conversation
    - You need to check user roles, join date, or other profile details
    - Someone asks "who is [user]?" or wants to know about a user
    - You want to see a user's avatar, status, or activity

    Args:
        user_id: The Discord user ID (without <@ brackets, just the number)

    Returns:
        Detailed user profile information including roles, join dates, status, etc.
    """
    try:
        context = get_discord_context()
        if not context or not context.message:
            raise ValueError("No Discord context available")

        # Convert string ID to int
        try:
            user_id_int = int(user_id.strip("<@>"))
        except ValueError:
            return f"Invalid user ID format: {user_id}"

        # Get user from guild if in server, otherwise try to fetch from client
        user = None
        member = None

        if context.message.guild:
            # Try to get as guild member first
            try:
                member = context.message.guild.get_member(user_id_int)
                user = member
            except (AttributeError, TypeError):
                pass

        # If not found as member, try to get as user from client
        if not user:
            try:
                user = await context.client.fetch_user(user_id_int)
            except (discord.NotFound, discord.HTTPException, AttributeError):
                return f"User with ID {user_id} not found or not accessible"

        # Build profile information
        result = []
        result.append(f"PROFILE: <@{user.id}>\n")

        # Basic info
        result.append(f"Username: {user.name}")
        result.append(f"Display Name: {user.display_name}")
        result.append(f"User ID: {user.id}")
        result.append(f"Bot: {'Yes' if user.bot else 'No'}")

        # Avatar
        if user.avatar:
            result.append(f"Avatar: {user.avatar.url}")
        else:
            result.append("Avatar: Default Discord avatar")

        # Account creation
        if user.created_at:
            result.append(
                f"Account Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

        # Guild-specific info (if member)
        if member and context.message.guild:
            result.append("\nSERVER INFO:")
            result.append(f"Server: {context.message.guild.name}")

            # Join date
            if member.joined_at:
                result.append(
                    f"Joined Server: {member.joined_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )

            # Status and activity
            if hasattr(member, "status"):
                result.append(f"Status: {member.status}")

            if hasattr(member, "activity") and member.activity:
                activity_type = str(member.activity.type).replace("ActivityType.", "")
                result.append(f"Activity: {activity_type} {member.activity.name}")

            # Roles
            if member.roles:
                # Skip @everyone role
                roles = [role for role in member.roles if role.name != "@everyone"]
                if roles:
                    role_names = [
                        role.name
                        for role in sorted(
                            roles, key=lambda x: x.position, reverse=True
                        )
                    ]
                    result.append(f"Roles: {', '.join(role_names)}")
                else:
                    result.append("Roles: None")

            # Nickname
            if member.nick:
                result.append(f"Nickname: {member.nick}")
        else:
            result.append("\nNot a member of current server or in DM")

        logger.info(f"👤 Retrieved profile for user {user.name} ({user.id})")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"❌ Failed to get user profile for {user_id}: {e}")
        return f"Failed to get user profile: {str(e)}"
