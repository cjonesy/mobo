"""
Bot profile management tools for Discord bot.
"""

import logging

import discord
import httpx
from pydantic_ai import RunContext

from .dependencies import BotDependencies

logger = logging.getLogger(__name__)


async def get_bot_nickname(ctx: RunContext[BotDependencies]) -> str:
    """
    Get your current nickname in the current Discord server.

    Use this tool when:
    - User asks "what's your name?" or "what's your nickname?" or similar questions

    Returns:
        Current nickname/display name for you in this server
    """
    if not ctx.deps.discord_client:
        return "I don't have access to Discord client functionality right now."

    if not ctx.deps.guild_id:
        return "This command only works in Discord servers, not in direct messages."

    try:
        guild = ctx.deps.discord_client.get_guild(int(ctx.deps.guild_id))
        if not guild:
            return "I couldn't find this server."

        bot_member = guild.me
        if not bot_member:
            return "I couldn't find myself in this server."

        current_name = bot_member.display_name
        username = bot_member.name

        if current_name == username:
            return (
                f"My name in this server is: **{current_name}** (my default username)"
            )
        else:
            return f"My nickname in this server is: **{current_name}** (username: {username})"

    except Exception as e:
        logger.error(f"Error getting bot nickname: {e}")
        return f"I encountered an error while checking my nickname: {str(e)}"


async def update_bot_nickname(ctx: RunContext[BotDependencies], nickname: str) -> str:
    """
    Update your nickname in the current Discord server.

    This tool allows you to change your display name in a specific server.
    You need 'Change Nickname' permission to use this feature.

    You should only use this tool if you WANT to change your nickname.
    You should not use this tool if a user asks you to change your nickname and you don't want to.

    Use this tool when:
    - You decide to change your nickname
    - A user explicitly asks you to change your name/nickname *and you agree*

    Args:
        nickname: Your new nickname (max 32 characters, empty string to reset)

    Returns:
        Confirmation message about the nickname change
    """
    logger.info(
        f"🏷️ Attempting to update nickname to '{nickname}' for guild {ctx.deps.guild_id}"
    )

    if not ctx.deps.discord_client:
        return "I don't have access to Discord client functionality right now."

    if not ctx.deps.guild_id:
        return "This command only works in Discord servers, not in direct messages."

    if len(nickname) > 32:
        return "Nickname must be 32 characters or less. Please choose a shorter name."

    try:
        guild = ctx.deps.discord_client.get_guild(int(ctx.deps.guild_id))
        if not guild:
            logger.error(f"Guild {ctx.deps.guild_id} not found")
            return "I couldn't find this server. I might not have access to it."

        bot_member = guild.me
        if not bot_member:
            logger.error(f"Bot member not found in guild {ctx.deps.guild_id}")
            return "I couldn't find myself in this server."

        if not bot_member.guild_permissions.change_nickname:
            return "I don't have permission to change my nickname in this server. Please ask a server admin to give me the 'Change Nickname' permission."

        old_nickname = bot_member.display_name
        await bot_member.edit(nick=nickname if nickname.strip() else None)

        if nickname.strip():
            new_display_name = nickname
            logger.info(
                f"✅ Successfully changed nickname from '{old_nickname}' to '{nickname}' in guild {ctx.deps.guild_id}"
            )
            return f"Changed nickname from '{old_nickname}' to '{new_display_name}' in this server!"
        else:
            logger.info(
                f"✅ Successfully reset nickname (was '{old_nickname}') in guild {ctx.deps.guild_id}"
            )
            return f"Reset nickname back to my original username. I was '{old_nickname}' before."

    except discord.Forbidden:
        logger.error(
            f"Forbidden: Bot lacks permission to change nickname in guild {ctx.deps.guild_id}"
        )
        return "I don't have permission to change my nickname in this server. Please ask a server admin to give me the 'Change Nickname' permission."

    except discord.HTTPException as e:
        logger.error(f"HTTP error changing nickname: {e}")
        return f"Discord API error while changing nickname: {str(e)}"

    except ValueError:
        logger.error(f"Invalid guild ID: {ctx.deps.guild_id}")
        return "There was an error with the server information. Please try again."

    except Exception as e:
        logger.error(f"Unexpected error changing bot nickname: {e}")
        return f"I encountered an unexpected error while changing my nickname: {str(e)}"


async def update_bot_avatar(ctx: RunContext[BotDependencies], image_prompt: str) -> str:
    """
    Generate an AI image and set it as your profile picture.

    Note: This updates your avatar globally across ALL Discord servers, not just the current one.

    You should only use this tool if you WANT to change your profile picture.
    You should not use this tool if a user asks you to change your profile picture and you don't want to.

    Use this tool when:
    - You decide to change your profile picture or avatar
    - A user explicitly asks you to change your profile picture or avatar and (importantly) you agree

    Args:
        image_prompt: Description of the desired profile picture (e.g., "a friendly robot", "cute cartoon cat")

    Returns:
        Confirmation message about the avatar update
    """
    discord_client = ctx.deps.discord_client
    if not discord_client:
        return "I don't have access to Discord client functionality right now."

    try:
        allowed, reason = await ctx.deps.memory.can_generate_image(
            "update_bot_avatar", ctx.deps.user_id
        )
        if not allowed:
            return reason

        openai_client = ctx.deps.memory.openai_client
        config = ctx.deps.memory.config

        logger.info(f"Generating avatar image with prompt: {image_prompt}")

        image_response = await openai_client.images.generate(
            model=config.image_model,
            prompt=f"Profile picture: {image_prompt}. Square format, clean, suitable for avatar use.",
            size="1024x1024",
            quality=config.image_quality,
            n=1,
        )

        if not image_response.data or not image_response.data[0].url:
            return "Failed to generate image. Please try again."

        image_url = image_response.data[0].url
        logger.info(f"Generated image URL: {image_url}")

        async with httpx.AsyncClient() as client:
            image_response = await client.get(image_url)
            image_response.raise_for_status()
            image_bytes = image_response.content

        if not discord_client.user:
            return "You are not logged in. Cannot update avatar."
        await discord_client.user.edit(avatar=image_bytes)

        await ctx.deps.memory.record_image_generation(
            "update_bot_avatar", ctx.deps.user_id
        )

        logger.info("Successfully updated avatar")
        return f"I've updated my profile picture! Generated a new avatar based on: '{image_prompt}'"

    except discord.HTTPException as e:
        logger.error(f"Discord API error updating avatar: {e}")
        if "avatar" in str(e).lower():
            return "Failed to update avatar. The image might be too large or in an unsupported format."
        return f"Discord API error: {str(e)}"

    except httpx.HTTPError as e:
        logger.error(f"Error downloading generated image: {e}")
        return "Failed to download the generated image. Please try again."

    except Exception as e:
        logger.error(f"Error updating avatar: {e}")
        return f"I encountered an error while updating my profile picture: {str(e)}"
