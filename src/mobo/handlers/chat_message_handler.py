import logging
from datetime import datetime, timedelta
from openai import OpenAI
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Message:
    def __init__(self, role, content, name=None, is_bot=False):
        self.role = role
        self.content = content
        self.name = name

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


class BotResponseThrottler:
    def __init__(self) -> None:
        self.responses = {}
        self.throttled_until = {}

    async def register_response(self, channel_id, max_responses):
        if channel_id not in self.responses:
            self.responses[channel_id] = 1
        self.responses[channel_id] += 1

        logger.warning(
            "Response registered, channel %s has %s responses - max is %s - throttle at",
            channel_id,
            self.responses[channel_id],
            max_responses, self.throttled_until[channel_id]
        )

        if self.responses[channel_id] >= max_responses:
            self.throttle(channel_id)

    async def _throttle(self, channel_id):
        logger.warning("Throttling %s", channel_id)
        self.throttled_until[channel_id] = datetime.now() + timedelta(seconds=60)
        self.responses[channel_id] = 0

    async def _unthrottle(self, channel_id):
        logger.warning("Unthrottling %s", channel_id)
        self.throttled_until.pop(channel_id, None)

    async def is_throttled(self, channel_id):
        if channel_id not in self.throttled_until:
            return False

        difference = datetime.now() - self.throttled_until[channel_id]

        logger.warning(
            "Checking if %s is throttled, %s seconds",
            channel_id,
            difference.total_seconds(),
        )

        if difference.total_seconds() > 60:
            self._unthrottle(channel_id)
            return False
        return True


class ChatMessageHandler(BaseHandler):
    def __init__(self) -> None:
        super().__init__()
        self.open_ai_client = OpenAI()
        self.history = ChannelHistoryManager()
        self.throttler = BotResponseThrottler()

    async def handle(self, message, bot):
        channel_id = str(message.channel.id)
        content = message.content

        if message.author.bot:
            if await self.throttler.is_throttled(channel_id):
                logger.warning("Throttled on channel %s ...", channel_id)
                return
            await self.throttler.register_response(channel_id, bot.config.max_bot_responses)

        self.history.add_message(channel_id, Message(role="user", content=content))

        completion = self.open_ai_client.chat.completions.create(
            model=bot.config.model,
            messages=[{"role": "system", "content": bot.config.personality}]
            + self.history.get_messages_dict(channel_id),
        )

        response = completion.choices[0].message.content
        await message.reply(response)

        self.history.add_message(
            channel_id, Message(role="assistant", content=response)
        )
        self.history.prune_messages(channel_id, bot.config.max_history_length)
