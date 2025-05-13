import random
import logging
import tempfile
import os
from datetime import datetime
from openai import OpenAI
from .base_handler import BaseHandler
import discord

_log = logging.getLogger()
_log.setLevel(logging.INFO)

MAX_DISCORD_LENGTH = 2000


class Message:
    def __init__(self, role, content, name=None, is_bot=False):
        self.role = role
        self.content = content
        self.name = name
        self.is_bot = is_bot

    def to_dict(self):
        return {
            attr: getattr(self, attr)
            for attr in ["role", "content", "name"]
            if getattr(self, attr) is not None
        }


class BotResponse:
    def __init__(self, text_content, image_url=None):
        self.text_content = text_content
        self.image_url = image_url


class ChannelHistoryManager:
    def __init__(self):
        self.history = {}

    def add_message(self, channel_id, message):
        if channel_id not in self.history:
            self.history[channel_id] = []
        self.history[channel_id].append(message)

    def get_messages(self, channel_id):
        return self.history.get(channel_id, [])

    def get_messages_dict(self, channel_id):
        return [message.to_dict() for message in self.get_messages(channel_id)]

    def prune_messages(self, channel_id, number_of_messages):
        if channel_id in self.history:
            self.history[channel_id] = self.history[channel_id][-number_of_messages:]

    def message_count(self, channel_id):
        response_count = 0
        if channel_id in self.history:
            response_count = len(self.history[channel_id])
        return response_count

    def bot_responses(self, channel_id):
        """
        Counts the number of bot messages in the history for a given channel_id.
        """
        response_count = 0
        if channel_id in self.history:
            response_count = sum(
                1 for message in self.history[channel_id] if message.is_bot
            )
        return response_count


class ChatMessageHandler(BaseHandler):
    def __init__(self) -> None:
        super().__init__()
        self.open_ai_client = OpenAI()
        self.history = ChannelHistoryManager()

    def _get_channel_members(self, channel):
        """Get a formatted list of members in the channel for the AI to reference."""
        member_info = []
        for member in channel.members:
            if not member.bot:  # Exclude bots from the list
                # Store both the mention format and display name
                member_info.append(
                    {"name": member.display_name, "mention": f"<@{member.id}>"}
                )

        # Randomize the order of members
        random.shuffle(member_info)

        return member_info

    async def _generate_response(self, message, bot, channel_id, system_message):
        """Generate a response using the LLM, potentially with an image."""
        can_generate_image = bot.config.can_generate_image()

        # Prepare the system message with image generation instructions if enabled
        if can_generate_image:
            # Extract relevant context from the message for image generation decisions
            message_content = message.content.strip()
            mentions_removed = message_content.replace(f"<@{bot.user.id}>", "").strip()

            system_message += (
                "\n\nIMPORTANT: Your response MUST be in the following JSON format:"
            )
            system_message += "\n```"
            system_message += "\n{"
            system_message += '\n  "response": "Your normal text response here",'
            system_message += '\n  "image_prompt": "Detailed description for image generation (only include if you want to generate an image)"'
            system_message += "\n}"
            system_message += "\n```"
            system_message += "\nIf you don't want to generate an image, simply omit the 'image_prompt' field completely."
            system_message += "\nThere is no need to generate an image for every response, only do so when it makes sense, or when you think it might be funny."
            system_message += "\n\nThe user's latest message is: '{}'".format(
                mentions_removed
            )

        # Generate text response from LLM
        completion = self.open_ai_client.chat.completions.create(
            model=bot.config.model,
            messages=[{"role": "system", "content": system_message}]
            + self.history.get_messages_dict(channel_id),
            temperature=bot.config.temperature,
        )

        bot_text_response = completion.choices[0].message.content

        # Parse JSON response if image generation is enabled
        if can_generate_image:
            try:
                import json
                import re

                # Extract JSON object from response, handling cases where there might be additional text
                json_match = re.search(r"\{[\s\S]*?\}", bot_text_response)
                if json_match:
                    json_str = json_match.group(0)
                    response_obj = json.loads(json_str)

                    # Extract text response and potential image prompt
                    if "response" in response_obj:
                        bot_text_response = response_obj["response"]

                    # Check if image prompt is provided
                    if "image_prompt" in response_obj and response_obj["image_prompt"]:
                        image_prompt = response_obj["image_prompt"]

                        try:
                            # Generate the image
                            image_response = self.open_ai_client.images.generate(
                                model=bot.config.image_model,
                                prompt=image_prompt,
                                size=bot.config.image_size,
                                quality="standard",
                                n=1,
                            )

                            # Store the image URL for Discord to display directly
                            image_url = image_response.data[0].url

                            # Increment the image count
                            bot.config.increment_image_count()

                            # Return the bot response with the image URL
                            return BotResponse(bot_text_response, image_url)
                        except Exception as e:
                            _log.error(f"Error generating image: {e}")
            except Exception as e:
                _log.error(
                    f"Error parsing JSON response: {e} - Response was: {bot_text_response}"
                )

        return BotResponse(bot_text_response, None)

    async def handle(self, message, bot):
        channel_id = str(message.channel.id)

        if not message.author.bot or (
            message.author.bot
            and self.history.bot_responses(channel_id) <= bot.config.max_bot_responses
        ):
            # Get channel members
            member_info = self._get_channel_members(message.channel)

            # Create system message with personality and channel members info
            system_message = bot.config.personality
            if member_info:
                system_message += "\n\nUsers you can mention in this Discord channel:"
                for member in member_info:
                    system_message += f"\n- To mention {member['name']}, use exactly: {member['mention']}"
                system_message += "\n\nIMPORTANT: NEVER use @everyone or @here mentions under any circumstances. Do not use @username format as it won't properly tag users."

            # First add the user message to history
            self.history.add_message(
                channel_id,
                Message(
                    role="user", content=message.content, is_bot=message.author.bot
                ),
            )

            # Generate the bot's response (text and possibly an image)
            bot_response = await self._generate_response(
                message, bot, channel_id, system_message
            )

            # Send the response
            if len(bot_response.text_content) <= MAX_DISCORD_LENGTH:
                if bot_response.image_url:
                    # Create an embed with the image
                    embed = discord.Embed()
                    embed.set_image(url=bot_response.image_url)
                    # Send the text response with the embed containing the image
                    await message.reply(content=bot_response.text_content, embed=embed)
                else:
                    # Send text-only response
                    await message.reply(bot_response.text_content)
            else:
                # Handle long messages
                chunks = [
                    bot_response.text_content[i : i + MAX_DISCORD_LENGTH]
                    for i in range(
                        0, len(bot_response.text_content), MAX_DISCORD_LENGTH
                    )
                ]

                # Send the first chunk as a reply, with image if available
                if bot_response.image_url:
                    # Create an embed with the image
                    embed = discord.Embed()
                    embed.set_image(url=bot_response.image_url)
                    # Send the first chunk with the embed
                    first_message = await message.reply(content=chunks[0], embed=embed)
                else:
                    first_message = await message.reply(chunks[0])

                # Send remaining chunks as follow-ups
                for chunk in chunks[1:]:
                    await first_message.channel.send(chunk)

            # Add the response to the history
            self.history.add_message(
                channel_id,
                Message(role="assistant", content=bot_response.text_content),
            )

        self.history.prune_messages(channel_id, bot.config.max_history_length)
