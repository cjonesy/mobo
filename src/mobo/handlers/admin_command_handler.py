from .base_handler import BaseHandler
from ..config import MoboConfig


class AdminCommandHandler(BaseHandler):
    async def handle(self, message, bot):
        if message.author.guild_permissions.administrator:
            response = ""
            parts = message.content.split(" ", 3)
            admin_command = parts[2] if len(parts) > 2 else None
            text = parts[3] if len(parts) > 3 else None

            command_handlers = {
                "help": self.handle_help,
                "get-personality": self.handle_get_personality,
                "set-personality": self.handle_set_personality,
                "set-personality-url": self.handle_set_personality_url,
                "reset-config": self.handle_reset_config,
                "get-model": self.handle_get_model,
                "set-model": self.handle_set_model,
                "enable-images": self.handle_enable_images,
                "disable-images": self.handle_disable_images,
                "set-image-model": self.handle_set_image_model,
                "set-image-limit": self.handle_set_image_limit,
                "get-image-quota": self.handle_get_image_quota,
            }

            handler = command_handlers.get(admin_command, self.handle_unknown_command)
            response = await handler(bot, text)
        else:
            response = "https://media.giphy.com/media/3eKdC7REvgOt2/giphy.gif"

        await message.reply(response)

    async def handle_help(self, bot, text):
        return "\n".join(
            [
                "Available commands:",
                "`get-personality` - Returns the current personality text",
                "`set-personality <text>` - Changes the bot's personality text",
                "`set-personality-url <text>` - Changes the bot's personality url and loads it",
                "`reset-config` - Resets the bot's personality to default",
                "`get-model` - Returns the current model",
                "`set-model <text>` - Changes the bot's model",
                "`enable-images` - Enables image generation",
                "`disable-images` - Disables image generation",
                "`set-image-model <text>` - Changes the image generation model (default: dall-e-3)",
                "`set-image-limit <number>` - Sets the daily image generation limit (default: 10)",
                "`get-image-quota` - Shows the remaining daily image quota",
            ]
        )

    async def handle_get_personality(self, bot, text):
        return f"```\n{bot.config.personality}\n```"

    async def handle_set_personality_url(self, bot, text):
        if text:
            bot.config.personality_url = text
            bot.config.personality = self.personality_from_url()
            return "Personality set."
        else:
            return "Error: No personality url provided"

    async def handle_set_personality(self, bot, text):
        if text:
            bot.config.personality = text
            return "Personality set."
        else:
            return "Error: No personality text provided"

    async def handle_reset_config(self, bot, text):
        bot.config = MoboConfig.from_env()
        return "Config reset."

    async def handle_get_model(self, bot, text):
        return f"`{bot.config.model}`"

    async def handle_set_model(self, bot, text):
        if text:
            bot.config.model = text
            return f"Model set to {text}."
        else:
            return "Error: No model text provided"

    async def handle_enable_images(self, bot, text):
        bot.config.enable_image_generation = True
        return "Image generation enabled."

    async def handle_disable_images(self, bot, text):
        bot.config.enable_image_generation = False
        return "Image generation disabled."

    async def handle_set_image_model(self, bot, text):
        if text:
            bot.config.image_model = text
            return f"Image model set to {text}."
        else:
            return "Error: No image model provided. Supported models include: dall-e-2, dall-e-3"

    async def handle_set_image_limit(self, bot, text):
        if text and text.isdigit():
            bot.config.max_daily_images = int(text)
            return f"Daily image limit set to {text}."
        else:
            return "Error: Please provide a valid number for the image limit."

    async def handle_get_image_quota(self, bot, text):
        remaining = bot.config.max_daily_images - bot.config.daily_image_count
        return f"Image quota: {remaining}/{bot.config.max_daily_images} images remaining today."

    async def handle_unknown_command(self, bot, text):
        return "Unknown command. Use `help` for a list of available commands."
