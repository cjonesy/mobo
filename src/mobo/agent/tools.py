"""Tools for the Discord bot agent."""

import logging
from typing import Optional, Any

import discord
import httpx
from langchain_core.tools import tool, BaseTool

from .user_profiles import UserProfileManager
from ..config import Config, get_config

logger = logging.getLogger(__name__)

# Global instances (will be initialized when tools are used)
_user_profile_manager: Optional[UserProfileManager] = None
_config: Optional[Config] = None
_discord_context: dict[str, Any] = {}


def _get_user_profile_manager() -> UserProfileManager:
    """Get or create user profile manager instance."""
    global _user_profile_manager
    if _user_profile_manager is None:
        _user_profile_manager = UserProfileManager()
    return _user_profile_manager


def _get_config() -> Config:
    """Get or create config instance."""
    global _config
    if _config is None:
        _config = get_config()
    return _config


def _set_discord_context(
    guild_member: discord.Member, guild_id: Optional[str] = None
) -> None:
    """Set Discord context for tools to use."""
    global _discord_context
    _discord_context = {"guild_member": guild_member, "guild_id": guild_id}


def _get_discord_context() -> Optional[dict[str, Any]]:
    """Get Discord context for tools."""
    global _discord_context
    return _discord_context


@tool
async def generate_image(prompt: str) -> Any:
    """Generate an image using DALL-E based on a text prompt.

    Use this tool when you want to create an image for the conversation.

    Args:
        prompt: Description of the image to generate

    Returns:
        Dictionary containing response data for structured processing on success,
        or error message string on failure
    """
    try:
        config = _get_config()

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.openai_api_key.get_secret_value())

        logger.info(f"Generating image with prompt: {prompt}")

        response = await client.images.generate(
            model=config.image_model,
            prompt=prompt,
            size=config.image_size,
            quality=config.image_quality,
            n=1,
        )

        if response.data and response.data[0].url:
            image_url = response.data[0].url
            logger.info(f"Generated image: {image_url}")

            async with httpx.AsyncClient() as http_client:
                image_response = await http_client.get(image_url)
                if image_response.status_code == 200:
                    import time

                    filename = f"generated_image_{int(time.time())}.png"

                    return {
                        "content": filename,
                        "artifact": {
                            "type": "image",
                            "filename": filename,
                            "data": image_response.content,
                        },
                    }
                else:
                    return (
                        f"ERROR: Could not download generated image. URL: {image_url}"
                    )
        else:
            return "ERROR: Image generation failed. No image was created."

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return f"ERROR: Image generation failed with exception: {str(e)}"


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

        discord_context = _get_discord_context()
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
async def get_current_chat_users(channel_id: str) -> str:
    """Get list of users currently active in the chat channel.

    Args:
        channel_id: Discord channel ID

    Returns:
        List of active users in the channel
    """
    try:
        discord_context = _get_discord_context()
        if not discord_context or not discord_context.get("guild_member"):
            return "ERROR: Discord server context not available"

        guild_member = discord_context["guild_member"]
        guild = guild_member.guild

        channel = guild.get_channel(int(channel_id))
        if not channel:
            return f"ERROR: Channel {channel_id} not found"

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


@tool
async def update_user_tone(user_id: str, tone: str) -> str:
    """Internal tool: Update user's interaction tone based on conversation analysis.

    This tool should ONLY be called when the AI detects tone patterns from natural
    conversation - never in response to direct user requests to change their tone.

    Args:
        user_id: Discord user ID
        tone: Detected tone (friendly, rude, neutral, etc.)

    Returns:
        Status message for internal logging
    """
    try:
        user_manager = _get_user_profile_manager()
        await user_manager.update_user_tone(user_id, tone)

        logger.info(f"Updated tone for user {user_id} to {tone}")
        return f"SUCCESS: User tone updated to {tone}"

    except Exception as e:
        logger.error(f"Error updating user tone: {e}")
        return f"ERROR: Failed to update user tone: {str(e)}"


@tool
async def add_user_interests(
    user_id: str, interests: str, interest_type: str = "likes"
) -> str:
    """Internal tool: Automatically add interests detected from user conversation.

    This tool should ONLY be called when the AI detects new interests from natural
    conversation - never in response to direct user requests to manage interests.

    Args:
        user_id: Discord user ID
        interests: Comma-separated list of interests detected from conversation
        interest_type: Either 'likes' or 'dislikes'

    Returns:
        Status message for internal logging
    """
    try:
        user_manager = _get_user_profile_manager()
        interest_list = [interest.strip() for interest in interests.split(",")]

        if interest_type.lower() == "likes":
            await user_manager.add_user_likes(user_id, interest_list)
            logger.info(f"Added likes for user {user_id}: {interest_list}")
            return f"SUCCESS: Added {', '.join(interest_list)} to user likes"
        elif interest_type.lower() == "dislikes":
            await user_manager.add_user_dislikes(user_id, interest_list)
            logger.info(f"Added dislikes for user {user_id}: {interest_list}")
            return f"SUCCESS: Added {', '.join(interest_list)} to user dislikes"
        else:
            return "ERROR: Invalid interest type (must be 'likes' or 'dislikes')"

    except Exception as e:
        logger.error(f"Error adding user interests: {e}")
        return f"ERROR: Failed to add user interests: {str(e)}"


@tool
async def remove_user_interests(
    user_id: str, interests: str, interest_type: str = "likes"
) -> str:
    """Internal tool: Remove interests when user indicates changed preferences.

    This tool should ONLY be called when the AI detects the user no longer likes/dislikes
    something based on natural conversation - never for direct interest management.

    Args:
        user_id: Discord user ID
        interests: Comma-separated list of interests to remove based on conversation
        interest_type: Either 'likes' or 'dislikes'

    Returns:
        Status message for internal logging
    """
    try:
        user_manager = _get_user_profile_manager()
        interest_list = [interest.strip() for interest in interests.split(",")]

        if interest_type.lower() == "likes":
            await user_manager.remove_user_likes(user_id, interest_list)
            logger.info(f"Removed likes for user {user_id}: {interest_list}")
            return f"SUCCESS: Removed {', '.join(interest_list)} from user likes"
        elif interest_type.lower() == "dislikes":
            await user_manager.remove_user_dislikes(user_id, interest_list)
            logger.info(f"Removed dislikes for user {user_id}: {interest_list}")
            return f"SUCCESS: Removed {', '.join(interest_list)} from user dislikes"
        else:
            return "ERROR: Invalid interest type (must be 'likes' or 'dislikes')"

    except Exception as e:
        logger.error(f"Error removing user interests: {e}")
        return f"ERROR: Failed to remove user interests: {str(e)}"


@tool
async def get_user_profile(user_id: str) -> str:
    """Get a user's profile information to provide personalized responses.

    This can be used when users ask about their preferences or when the AI needs
    context for personalized responses.

    Args:
        user_id: Discord user ID

    Returns:
        User profile information
    """
    try:
        user_manager = _get_user_profile_manager()
        profile = await user_manager.get_user_profile(user_id)

        tone = profile.get("tone", "neutral")
        likes = profile.get("likes", [])
        dislikes = profile.get("dislikes", [])

        profile_text = f"User interaction style: {tone}"
        if likes:
            profile_text += f"\nLikes: {', '.join(likes[:5])}"
        if dislikes:
            profile_text += f"\nDislikes: {', '.join(dislikes[:5])}"

        return profile_text

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return f"ERROR: Failed to retrieve user profile: {str(e)}"


def get_all_tools() -> list[BaseTool]:
    """Get all available tools for the LangGraph agent."""
    return [
        generate_image,
        change_nickname,
        get_current_chat_users,
        mention_user,
        update_user_tone,
        add_user_interests,
        remove_user_interests,
        get_user_profile,
    ]


def set_discord_context(
    guild_member: discord.Member, guild_id: Optional[str] = None
) -> None:
    """Set Discord context for tools to use. Called by agent before tool execution."""
    _set_discord_context(guild_member, guild_id)
