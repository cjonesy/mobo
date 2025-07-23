"""
Discord client implementation using PydanticAI agents with memory management.
"""

import discord
import logging

from ..ai import create_discord_agent, process_discord_message
from ..ai.memory_manager import memory_manager
from ..utils.config import get_config

logger = logging.getLogger(__name__)

config = get_config()

discord_agent = create_discord_agent()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """Event handler for when the bot is ready."""
    if client.user:
        logger.info(f"🤖 {client.user} has connected to Discord!")

        try:
            await memory_manager.initialize_database()
            logger.info("📊 Database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")


@client.event
async def on_message(message):
    """Event handler for incoming Discord messages."""
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Ignore empty messages
    if not message.content.strip():
        return

    # Only respond if bot is mentioned or if message is a reply to the bot
    bot_mentioned = client.user in message.mentions
    is_reply_to_bot = False

    # Check if this is a reply to the bot
    if message.reference and message.reference.message_id:
        try:
            referenced_message = await message.channel.fetch_message(
                message.reference.message_id
            )
            is_reply_to_bot = referenced_message.author == client.user
        except discord.NotFound:
            # Referenced message not found, ignore
            pass
        except Exception as e:
            logger.error(f"Error fetching referenced message: {e}")

    # If not mentioned and not replying to bot, ignore the message
    if not bot_mentioned and not is_reply_to_bot:
        return

    try:
        # Show typing indicator while processing
        async with message.channel.typing():
            # Get guild ID if in a server, None if in DM
            guild_id = str(message.guild.id) if message.guild else None

            # Process the message through PydanticAI agent
            response = await process_discord_message(
                agent=discord_agent,
                memory=memory_manager,
                user_message=message.content,
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
                username=message.author.name,
                discord_client=client,
                guild_id=guild_id,
            )

            if response:
                await message.reply(response)

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.reply("Sorry, I encountered an error processing your message.")


def run_bot():
    """Run the Discord bot."""
    try:
        client.run(config.discord_token.get_secret_value())
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
