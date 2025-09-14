"""
Discord tools with context injection - no more circular imports!

This module contains Discord-specific tools that receive context via
dependency injection instead of importing it themselves.
"""

import logging
from typing import List
from langchain_core.runnables import RunnableConfig
from .common import registered_tool

logger = logging.getLogger(__name__)


@registered_tool()
async def list_custom_emoji(config: RunnableConfig) -> str:
    """
    List all custom emoji available to the bot for use in responses and reactions.

    After calling this tool, you can use the emoji in your response.

    For MESSAGE EMBEDDING (in your response text):
    - Static emoji: Use format <:name:id> (e.g., <:add_reaction:123456>)
    - Animated emoji: Use format <a:name:id> (e.g., <a:excited:789012>)

    For REACTIONS (with add_reaction tool):
    - Just use the name (e.g., "add_reaction")

    Returns:
        Available emoji with name:id format for you to use
    """
    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not client:
            raise ValueError("No Discord client available")

        result = []

        # Add custom emoji from current guild if available
        if message and message.guild:
            emojis = await client.get_guild_emojis(message.guild)

            static_emoji = []
            animated_emoji = []

            for emoji in emojis:
                if emoji["animated"]:
                    animated_emoji.append(
                        f"{emoji['name']}:{emoji['id']} (<a:{emoji['name']}:{emoji['id']}>)"
                    )
                else:
                    static_emoji.append(
                        f"{emoji['name']}:{emoji['id']} (<:{emoji['name']}:{emoji['id']}>)"
                    )

            if static_emoji:
                result.append(f"📝 **Static Emoji ({len(static_emoji)}):**")
                result.extend(static_emoji[:20])  # Limit to first 20

            if animated_emoji:
                result.append(f"🎬 **Animated Emoji ({len(animated_emoji)}):**")
                result.extend(animated_emoji[:10])  # Limit to first 10

            if len(static_emoji) > 20:
                result.append(f"... and {len(static_emoji) - 20} more static emoji")
            if len(animated_emoji) > 10:
                result.append(f"... and {len(animated_emoji) - 10} more animated emoji")

        if not result:
            result.append("No custom emoji available in this server.")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"❌ Failed to list custom emoji: {e}")
        return f"❌ Failed to list custom emoji: {e}"


@registered_tool()
async def add_reaction(config: RunnableConfig, emoji: str) -> str:
    """
    Add a reaction to the message the user just sent.

    Use this when someone asks you to react or when you want to show emotion/acknowledgment.

    Args:
        emoji: Emoji to add as reaction (Unicode emoji like "👍" or custom emoji name like "thumbsup")

    Returns:
        Empty string (reactions don't need text responses)
    """
    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not message or not client:
            raise ValueError("No message or client available")

        await client.add_reaction_to_message(message, emoji)
        logger.info(f"✅ Reaction {emoji} added successfully")

        return ""

    except Exception as e:
        logger.error(f"❌ Failed to add reaction {emoji}: {e}")
        return ""


@registered_tool()
async def create_poll(
    config: RunnableConfig,
    question: str,
    options: List[str],
    duration_hours: int = 24,
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
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not message or not client:
            raise ValueError("No Discord context available for poll creation")

        logger.info(f"🗳️ Creating poll: {question[:50]}... with {len(options)} options")

        await client.create_poll_in_channel(
            message.channel, question, options, duration_hours
        )

        logger.info(f"✅ Poll created successfully with {len(options)} options")
        return f'✅ Created poll: "{question}" with {len(options)} options for {duration_hours} hours'

    except Exception as e:
        logger.error(f"❌ Failed to create poll: {e}")
        return f"❌ {str(e)}"


@registered_tool()
async def set_activity(
    config: RunnableConfig,
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

    Args:
        activity_type: Type of activity ("playing", "listening", "watching", "streaming", "competing")
        activity_name: What you're doing (e.g., "with Python code", "to music", "Netflix")

    Returns:
        Confirmation of activity change
    """
    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        if not client:
            raise ValueError("No Discord client available in configuration")

        await client.set_activity(activity_type, activity_name)
        logger.info(f"✅ Activity set to '{activity_type} {activity_name}'")

        return (
            f"✅ Now {activity_type} {activity_name}"
            if activity_name
            else "✅ Activity cleared"
        )

    except Exception as e:
        logger.error(f"❌ Failed to set activity: {e}")
        return f"❌ {str(e)}"


@registered_tool()
async def list_chat_users(config: RunnableConfig) -> str:
    """
    Get a list of users in the current Discord channel or server.

    Use this tool when someone asks about who's online, who's in the channel,
    or wants to know about other users present.

    Returns:
        List of users with their basic info
    """
    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not message or not client:
            raise ValueError("No message or client available")

        users_info = await client.get_channel_users(message.channel, client.user)

        if not users_info or "error" in users_info:
            return "❌ Could not retrieve user list"

        result = []
        result.append(f"👥 **Users in #{message.channel.name}:**")

        # Handle the actual data format returned by get_channel_users
        if "humans" in users_info:
            humans = users_info["humans"]
            if humans:
                result.append(f"👤 **Humans ({len(humans)}):**")
                for user in humans:
                    status = user.get("status", "offline")
                    status_emoji = {"online": "🟢", "idle": "🟡", "dnd": "🔴", "offline": "⚫"}.get(status, "❓")
                    result.append(f"  • {user['name']} {status_emoji}")

        if "bots" in users_info:
            bots = users_info["bots"]
            if bots:
                result.append(f"🤖 **Bots ({len(bots)}):**")
                for user in bots[:10]:  # Limit to 10 bots
                    status = user.get("status", "offline")
                    status_emoji = {"online": "🟢", "idle": "🟡", "dnd": "🔴", "offline": "⚫"}.get(status, "❓")
                    result.append(f"  • {user['name']} {status_emoji}")
                if len(bots) > 10:
                    result.append(f"  ... and {len(bots) - 10} more bots")

        # Add total count
        if "total" in users_info:
            result.append(f"\n**Total: {users_info['total']} users**")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}")
        return f"❌ {str(e)}"


@registered_tool()
async def get_user_profile(
    config: RunnableConfig, user_mention: str = ""
) -> str:
    """
    Get detailed profile information about a Discord user.

    Use this when someone asks about a specific user, wants to know about someone,
    or mentions checking someone's profile.

    Args:
        user_mention: User to look up (e.g., "@username" or "username").
                     If empty, shows info about the message author.

    Returns:
        Detailed user profile information
    """
    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not message or not client:
            raise ValueError("No message or client available")

        # Determine target user
        if user_mention:
            # Extract user ID from mention or search by username
            user_id = user_mention.strip("<@!>")
            if user_id.isdigit():
                target_user_id = user_id
            else:
                return f"❌ Could not find user: {user_mention}"
        else:
            # Default to message author
            target_user_id = str(message.author.id)

        # Get user profile
        user_profile = await client.get_user_profile(target_user_id, message.guild)

        if not user_profile or "error" in user_profile:
            return "❌ Could not retrieve profile for user"

        # Format profile information
        result = []
        result.append(
            f"👤 **User Profile: {user_profile.get('display_name', 'Unknown')}**"
        )

        if user_profile.get("username"):
            result.append(f"📝 Username: @{user_profile['username']}")

        if user_profile.get("status"):
            status_emoji = {
                "online": "🟢",
                "idle": "🟡",
                "dnd": "🔴",
                "offline": "⚫",
            }.get(user_profile["status"], "❓")
            result.append(f"{status_emoji} Status: {user_profile['status'].title()}")

        if user_profile.get("activity"):
            result.append(f"🎮 Activity: {user_profile['activity']}")

        if user_profile.get("joined_at"):
            result.append(f"📅 Joined Server: {user_profile['joined_at']}")

        if user_profile.get("created_at"):
            result.append(f"🎂 Account Created: {user_profile['created_at']}")

        if user_profile.get("roles"):
            roles = user_profile["roles"][:5]  # Limit to 5 roles
            result.append(f"🏷️ Roles: {', '.join(roles)}")
            if len(user_profile["roles"]) > 5:
                result.append(f"   ... and {len(user_profile['roles']) - 5} more")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"❌ Failed to get user profile: {e}")
        return f"❌ {str(e)}"
