import logging
import discord

from ..handlers import AdminCommandHandler, ChatMessageHandler

class Mobo(discord.Client):
    def __init__(self, config):
        super().__init__(intents=discord.Intents.all())
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.setLevel(logging.getLevelName(self.config.log_level))
        self.logger.info("Logger for %s initialized", self.__class__.__name__)
        self.handlers = {
            "admin": AdminCommandHandler(self.config),
            "chat": ChatMessageHandler(self.config),
        }

    async def on_ready(self):
        print(f"We have logged in as {self.user}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if self.user.mentioned_in(message):
            async with message.channel.typing():
                if '!admin' in message.content:
                    await self.handlers["admin"].handle(message, self)
                else:
                    await self.handlers["chat"].handle(message, self)
                return

    def run(self):
        super().run(token=self.config.discord_token)
