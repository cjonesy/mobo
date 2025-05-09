import logging
from datetime import datetime
from openai import OpenAI
from .base_handler import BaseHandler

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
        members = []
        for member in channel.members:
            if not member.bot:  # Exclude bots from the list
                members.append(f"@{member.display_name}")
        return members

    async def handle(self, message, bot):
        channel_id = str(message.channel.id)

        if not message.author.bot or (
            message.author.bot
            and self.history.bot_responses(channel_id) <= bot.config.max_bot_responses
        ):
            self.history.add_message(
                channel_id,
                Message(
                    role="user", content=message.content, is_bot=message.author.bot
                ),
            )

            # Get channel members
            channel_members = self._get_channel_members(message.channel)

            # Create system message with personality and channel members info
            system_message = bot.config.personality
            if channel_members:
                system_message += f"\n\nUsers in this Discord channel: {', '.join(channel_members)}. You can mention any of them by using their name with an @ symbol."

            completion = self.open_ai_client.chat.completions.create(
                model=bot.config.model,
                messages=[{"role": "system", "content": system_message}]
                + self.history.get_messages_dict(channel_id),
                temperature=bot.config.temperature,
            )

            bot_response = completion.choices[0].message.content

            if len(bot_response) <= MAX_DISCORD_LENGTH:
                await message.reply(bot_response)
            else:
                chunks = [
                    bot_response[i : i + MAX_DISCORD_LENGTH]
                    for i in range(0, len(bot_response), MAX_DISCORD_LENGTH)
                ]

                # Send the first chunk as a reply to the original message
                first_message = await message.reply(chunks[0])

                # Send remaining chunks as follow-ups
                for chunk in chunks[1:]:
                    await first_message.channel.send(chunk)

            self.history.add_message(
                channel_id,
                Message(role="assistant", content=bot_response),
            )

        self.history.prune_messages(channel_id, bot.config.max_history_length)
