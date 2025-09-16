"""
Discord tools with LangChain native patterns.

This module contains Discord-specific tools using native LangChain @tool decorator
with structured Pydantic responses for type safety and better integration.
"""

import logging
import aiohttp
from typing import List
from urllib.parse import urlparse
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from .common import register_tool
from .schemas import (
    EmojiListResponse,
    EmojiData,
    SimpleResponse,
    UserListResponse,
    UserData,
    UserProfileResponse,
    UserProfile,
    StickerListResponse,
    StickerData,
    AvatarUpdateResponse,
    UrlSummaryResponse,
)

logger = logging.getLogger(__name__)


@tool
async def list_custom_emoji(config: RunnableConfig) -> EmojiListResponse:
    """Lists custom server emoji available to the bot for use in responses and reactions.

    Returns formatted custom emoji data with ready-to-use strings for embedding in messages
    or adding as reactions. Note: This only shows custom server emoji - you can also use
    standard Unicode emoji like 😎, 👍, ❤️, 🎉, etc. without calling this tool.

    Examples: Discovering available custom emoji, finding specific custom emoji for messages,
    checking what custom reactions are possible.

    JSON Response Structure:
        On success:
        - success (bool): True if emoji list was retrieved successfully
        - emojis (array): Array of emoji objects, each containing:
          - name (str): Emoji name for use in reactions
          - message_embed_format (str): Ready-to-use format for message embedding
          - reaction_format (str): Ready-to-use format for reactions
          - id (str): Discord emoji ID
        - total (int): Total number of emoji available

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord client context.

    Returns:
        Structured response containing emoji data or error information.
    """
    logger.info("😃 Calling list_custom_emoji")

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")

        if not client:
            raise ValueError("No Discord client available")

        emojis = [
            EmojiData(
                name=emoji.name,
                message_embed_format=f"<:{emoji.name}:{emoji.id}>",
                reaction_format=emoji.name,
                id=str(emoji.id),
            )
            for emoji in client.emojis
            if not emoji.animated
        ]

        logger.info(f"✅ Found {len(emojis)} emoji")

        return EmojiListResponse(
            success=True,
            emojis=emojis,
            total=len(emojis),
        )

    except Exception as e:
        logger.error(f"❌ Failed to list emoji: {e}")
        return EmojiListResponse(success=False, error=str(e))


@tool
async def add_reaction(config: RunnableConfig, emoji: str) -> str:
    """Adds a reaction emoji to the user's message.

    Reactions are a way to express emotion, acknowledgment, or response without sending text.
    You can use standard Unicode emoji directly (like 👍, 😂, ❤️, 🎉, 😎) or use the
    list_custom_emoji tool to find custom server emoji. Standard emoji work great for most reactions!

    Examples: Showing approval (👍), expressing laughter (😂), acknowledging a message,
    reacting to exciting news (🎉), showing agreement or disagreement.

    Args:
        config: Runtime configuration containing Discord client context.
        emoji: Emoji to add as reaction (Unicode emoji like "👍" or custom emoji name like "thumbsup").

    Returns:
        Empty string (reactions don't need text responses).
    """
    logger.info("🧐 Calling add_reaction", extra={"emoji": emoji})

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


@tool
async def create_poll(
    config: RunnableConfig,
    question: str,
    options: List[str],
    duration_hours: int = 1,
) -> SimpleResponse:
    """Creates a Discord poll in the current channel with multiple choice options.

    Polls allow users to vote on questions and see real-time results.
    Examples: Deciding between options, gathering opinions, making group choices,
    voting on topics, scheduling decisions, preference surveys.

    JSON Response Structure:
        On success:
        - success (bool): True if poll was created successfully

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord client context.
        question: The poll question to ask.
        options: List of 2-10 poll options/answers (must have at least 2, max 10).
        duration_hours: How long the poll should run (1-168 hours, default 1).

    Returns:
        JSON string with success status and error details if applicable.
    """
    logger.info(
        "🗳️ Calling create_poll",
        extra={
            "question": question,
            "options": options,
            "duration_hours": duration_hours,
        },
    )

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
        return SimpleResponse(success=True)

    except Exception as e:
        logger.error(f"❌ Failed to create poll: {e}")
        return SimpleResponse(success=False, error=str(e))


@tool
async def set_activity(
    config: RunnableConfig,
    activity_type: str = "playing",
    activity_name: str = "",
) -> SimpleResponse:
    """Updates the bot's activity status that appears in the user list.

    Activity status shows what the bot is currently doing or engaged with,
    visible to all users in the server. Examples: Reflecting conversation topics
    ("listening to music discussions"), showing engagement ("playing word games"),
    indicating focus areas, matching the mood of the channel.

    JSON Response Structure:
        On success:
        - success (bool): True if activity was set successfully

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord client context.
        activity_type: Type of activity ("playing", "listening", "watching", "streaming", "competing").
        activity_name: What you're doing (e.g., "with Python code", "to music", "Netflix").

    Returns:
        JSON string with success status and error details if applicable.
    """
    logger.info(
        "🎧 Calling set_activity",
        extra={"activity_type": activity_type, "activity_name": activity_name},
    )

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        if not client:
            raise ValueError("No Discord client available in configuration")

        await client.set_activity(activity_type, activity_name)
        logger.info(f"✅ Activity set to '{activity_type} {activity_name}'")

        return SimpleResponse(success=True)

    except Exception as e:
        logger.error(f"❌ Failed to set activity: {e}")
        return SimpleResponse(success=False, error=str(e))


@tool
async def list_chat_users(config: RunnableConfig) -> UserListResponse:
    """Retrieves information about all users currently in the Discord channel.

    Provides detailed user data including names, IDs, mentions, and online status
    for both human users and bots. Examples: Checking who's active, finding specific
    users, getting mention formats, understanding channel participation, seeing online status.

    JSON Response Structure:
        On success:
        - success (bool): True if user list was retrieved successfully
        - users (array): Array of human users in the channel, each containing:
          - name (str): User's username
          - id (str): Discord user ID
          - display_name (str): Server-specific display name
          - global_name (str): Global display name (or null)
          - nickname (str): Server-specific nickname (or null)
          - mention (str): Mention format (@user)
          - status (str): Online status (online/idle/dnd/offline/unknown)
        - bots (array): Array of bot users in the channel with same structure as users
        - total (int): Total number of users and bots

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord message context.

    Returns:
        JSON string with user data including names, IDs, mentions, and status.
    """
    logger.info("🧍 Calling list_chat_users")

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        message = config["configurable"].get("discord_message")

        if not message:
            raise ValueError("No message available")

        users = [
            UserData(
                name=member.name,
                id=str(member.id),
                display_name=member.display_name,
                global_name=member.global_name,
                nickname=member.nick,
                mention=member.mention,
                status=str(member.status) if hasattr(member, "status") else "unknown",
            )
            for member in message.channel.members
            if not member.bot
        ]

        bots = [
            UserData(
                name=member.name,
                id=str(member.id),
                display_name=member.display_name,
                global_name=member.global_name,
                nickname=member.nick,
                mention=member.mention,
                status=str(member.status) if hasattr(member, "status") else "unknown",
            )
            for member in message.channel.members
            if member.bot
        ]

        logger.info(f"✅ Found {len(users)} users and {len(bots)} bots")

        return UserListResponse(
            success=True,
            users=users,
            bots=bots,
            total=len(users) + len(bots),
        )

    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}")
        return UserListResponse(success=False, error=str(e))


@tool
async def list_stickers(config: RunnableConfig) -> StickerListResponse:
    """Lists all stickers available to the bot (server-specific custom stickers).

    Stickers are large emoji-like images that can be sent as messages
    to express emotions or reactions. This shows custom stickers uploaded to the current server.
    Note: Standard Discord sticker packs are not accessible through the Discord API.
    After calling this tool, you can use the send_sticker tool to send any of these stickers.
    Examples: Discovering available stickers, finding appropriate reactions, checking what visual responses are possible.

    JSON Response Structure:
        On success:
        - success (bool): True if sticker list was retrieved successfully
        - stickers (array): Array of available stickers, each containing:
          - name (str): Sticker name for use with send_sticker
          - id (str): Discord sticker ID
          - description (str): Description of what the sticker shows

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord client context.

    Returns:
        JSON string with sticker data including names, IDs, and descriptions.
    """
    logger.info("🎨 Calling list_stickers")

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")

        if not client:
            raise ValueError("No Discord client available")

        # Get server-specific custom stickers
        server_stickers = [
            StickerData(
                name=sticker.name,
                id=str(sticker.id),
                description=sticker.description or f"Custom server sticker: {sticker.name}",
            )
            for sticker in client.stickers
            if sticker.available
        ]

        # Note: Discord.py doesn't provide access to standard Discord sticker packs
        # Only server-specific custom stickers are available through the API
        all_stickers = server_stickers

        logger.info(f"✅ Found {len(server_stickers)} server stickers")

        return StickerListResponse(success=True, stickers=all_stickers)

    except Exception as e:
        logger.error(f"❌ Failed to list stickers: {e}")
        return StickerListResponse(success=False, error=str(e))


@tool
async def send_sticker(
    config: RunnableConfig, sticker_name: str, message_text: str = ""
) -> SimpleResponse:
    """Sends a sticker to the current channel, optionally with accompanying text.

    Stickers are large animated or static images that can express emotions,
    reactions, or add visual flair to conversations. Examples: Celebrating
    achievements, expressing emotions visually, adding humor, responding with
    animated reactions, enhancing message impact.

    JSON Response Structure:
        On success:
        - success (bool): True if sticker was sent successfully

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord client context.
        sticker_name: Name of the sticker to send (from list_stickers).
        message_text: Optional text message to include with the sticker.

    Returns:
        JSON string with success status and error details if applicable.
    """
    logger.info("🌟 Calling send_sticker", extra={"sticker_name": sticker_name})

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not message or not client:
            raise ValueError("No message or client available")

        logger.info(f"🌟 Sending sticker: {sticker_name}")

        await client.send_sticker_to_channel(
            message.channel, sticker_name, message_text
        )

        logger.info(f"✅ Sticker {sticker_name} sent successfully")
        return SimpleResponse(success=True)

    except Exception as e:
        logger.error(f"❌ Failed to send sticker {sticker_name}: {e}")
        return SimpleResponse(success=False, error=str(e))


@tool
async def get_user_profile(config: RunnableConfig, user: str) -> UserProfileResponse:
    """Retrieves detailed profile information about a specific Discord user.

    Provides comprehensive user data including account details, server information,
    roles, status, and activity. Examples: Learning about mentioned users, checking
    roles and permissions, seeing join dates, understanding user status, getting
    activity information.

    JSON Response Structure:
        On success:
        - success (bool): True if profile was retrieved successfully
        - profile (object): User profile data containing:
          - name (str): User's display name
          - id (str): Discord user ID
          - display_name (str): Server-specific display name
          - global_name (str): Global display name (or null)
          - mention (str): Mention format (@user)
          - nickname (str): Server-specific nickname (or null)
          - bot (bool): True if user is a bot
          - joined_at (str): When user joined this server (ISO format)
          - created_at (str): When user account was created (ISO format)
          - roles (array): Array of role names the user has
          - status (str): Online status (online/idle/dnd/offline)
          - avatar_url (str): URL to user's avatar image
          - activity (str): Current activity (e.g., "playing with Python code")

        On error:
        - success (bool): False
        - error (str): Description of what went wrong

    Args:
        config: Runtime configuration containing Discord client context.
        user: User to look up (e.g., "@username" or "username").

    Returns:
        JSON string with user profile data including roles, status, and activity.
    """
    logger.info("🙇 Calling get_user_profile", extra={"user": user})

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not message or not client:
            raise ValueError("No message or client available")

        user_profile_data = await client.get_user_profile(user, message.guild)

        if not user_profile_data or "error" in user_profile_data:
            return UserProfileResponse(
                success=False, error="Could not retrieve profile for user"
            )

        # Convert to structured UserProfile
        profile = UserProfile(**user_profile_data)

        logger.info(f"✅ Found user profile for {user}")

        return UserProfileResponse(success=True, profile=profile)

    except Exception as e:
        logger.error(f"❌ Failed to get user profile: {e}")
        return UserProfileResponse(success=False, error=str(e))


@tool
async def generate_and_set_avatar(
    config: RunnableConfig,
    prompt: str,
    guild_only: bool = False
) -> AvatarUpdateResponse:
    """Generates a new profile picture using DALL-E and sets it as the bot's avatar.

    Creates a custom avatar image based on your description and updates the bot's profile picture.
    Can set the avatar globally (everywhere) or attempt guild-specific if supported.

    Examples: Creating themed avatars, seasonal updates, matching server aesthetics,
    expressing personality changes, responding to events or celebrations.

    Args:
        config: Runtime configuration containing Discord client context.
        prompt: Description of the desired avatar (e.g., "a friendly robot with blue eyes").
        guild_only: If True, try to set guild-specific avatar only (may not be supported).

    Returns:
        Structured response with image URL, success status, and scope information.
    """
    logger.info(f"🎨 Calling generate_and_set_avatar", extra={"prompt": prompt[:50], "guild_only": guild_only})

    try:
        if not config or "configurable" not in config:
            raise ValueError("No configuration available")

        client = config["configurable"].get("discord_client")
        message = config["configurable"].get("discord_message")

        if not client:
            raise ValueError("No Discord client available")

        # Import here to avoid circular imports and to use the same config
        from ..config import settings
        from openai import AsyncOpenAI

        if not settings.openai.api_key:
            return AvatarUpdateResponse(
                success=False,
                error="OpenAI API key not configured for image generation"
            )

        # Generate image with DALL-E
        logger.info(f"🎨 Generating avatar image with prompt: {prompt}")

        openai_client = AsyncOpenAI(
            api_key=settings.openai.api_key.get_secret_value(),
            base_url="https://api.openai.com/v1",
        )

        image_response = await openai_client.images.generate(
            prompt=f"Profile picture avatar: {prompt}. Clean, clear, suitable for Discord profile picture.",
            n=1,
            size="1024x1024",  # DALL-E 3 minimum size, will be resized for Discord
            quality="standard",
            model="dall-e-3",
        )

        image_url = image_response.data[0].url
        logger.info(f"✅ Generated image: {image_url}")

        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to download image: HTTP {resp.status}")
                image_data = await resp.read()

        logger.info(f"📥 Downloaded image data ({len(image_data)} bytes)")

        # Try to set the avatar
        avatar_set = False
        scope = None
        additional_message = None

        try:
            if guild_only and message and hasattr(message, 'guild') and message.guild:
                # Try guild-specific avatar (this may not be supported for bots)
                try:
                    guild_member = message.guild.get_member(client.user.id)
                    if guild_member and hasattr(guild_member, 'edit'):
                        await guild_member.edit(avatar=image_data)
                        avatar_set = True
                        scope = "guild"
                        logger.info(f"✅ Set guild-specific avatar for {message.guild.name}")
                    else:
                        raise Exception("Guild avatar setting not supported for bots")
                except Exception as e:
                    logger.warning(f"⚠️ Guild avatar failed: {e}, falling back to global")
                    additional_message = f"Guild avatar failed ({str(e)}), set globally instead"
                    # Fall through to global setting

            if not avatar_set:
                # Set global avatar
                await client.user.edit(avatar=image_data)
                avatar_set = True
                scope = "global"
                logger.info("✅ Set global bot avatar")

        except Exception as avatar_error:
            logger.error(f"❌ Failed to set avatar: {avatar_error}")
            return AvatarUpdateResponse(
                success=False,
                error=f"Avatar generation succeeded but setting failed: {str(avatar_error)}",
                image_url=image_url,
                avatar_set=False
            )

        return AvatarUpdateResponse(
            success=True,
            image_url=image_url,
            avatar_set=avatar_set,
            scope=scope,
            message=additional_message or f"Avatar successfully set ({scope})"
        )

    except Exception as e:
        logger.error(f"❌ Failed to generate and set avatar: {e}")
        return AvatarUpdateResponse(success=False, error=str(e))


# Register all tools with the global registry
register_tool(list_custom_emoji)
register_tool(add_reaction)
register_tool(create_poll)
register_tool(set_activity)
register_tool(list_chat_users)
register_tool(list_stickers)
register_tool(send_sticker)
register_tool(get_user_profile)
register_tool(generate_and_set_avatar)
