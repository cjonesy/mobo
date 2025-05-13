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
                "get-temperature": self.handle_get_temperature,
                "set-temperature": self.handle_set_temperature,
                "get-top-p": self.handle_get_top_p,
                "set-top-p": self.handle_set_top_p,
                "get-randomness": self.handle_get_randomness,
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
                "`get-randomness` - Shows whether temperature or top_p is being used",
                "`get-temperature` - Returns the current temperature setting (if used)",
                "`set-temperature <value>` - Sets the model temperature (0.0-2.0) and disables top_p",
                "`get-top-p` - Returns the current top_p setting (if used)",
                "`set-top-p <value>` - Sets the model top_p (0.0-1.0) and disables temperature",
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
        return f"Model: `{bot.config.model}`"

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

    async def handle_get_randomness(self, bot, text):
        if bot.config.temperature is not None:
            return f"Using temperature: `{bot.config.temperature}`"
        elif bot.config.top_p is not None:
            return f"Using top_p: `{bot.config.top_p}`"
        else:
            return "No randomness parameter is set"

    async def handle_get_temperature(self, bot, text):
        if bot.config.temperature is not None:
            return f"Temperature: `{bot.config.temperature}`"
        else:
            return "Temperature is not active. Currently using top_p."

    async def handle_set_temperature(self, bot, text):
        if text:
            try:
                temp = float(text)
                if 0.0 <= temp <= 2.0:
                    # Use the set_temperature method to ensure top_p is cleared
                    bot.config.set_temperature(temp)
                    return f"Temperature set to {temp}. (top_p disabled)"
                else:
                    return "Error: Temperature must be between 0.0 and 2.0."
            except ValueError:
                return "Error: Please provide a valid number for temperature."
        else:
            return "Error: No temperature provided. Please provide a value between 0.0 and 2.0."

    async def handle_get_top_p(self, bot, text):
        if bot.config.top_p is not None:
            return f"Top_p: `{bot.config.top_p}`"
        else:
            return "Top_p is not active. Currently using temperature."

    async def handle_set_top_p(self, bot, text):
        if text:
            try:
                top_p = float(text)
                if 0.0 <= top_p <= 1.0:
                    # Use the set_top_p method to ensure temperature is cleared
                    bot.config.set_top_p(top_p)
                    return f"Top_p set to {top_p}. (temperature disabled)"
                else:
                    return "Error: Top_p must be between 0.0 and 1.0."
            except ValueError:
                return "Error: Please provide a valid number for top_p."
        else:
            return "Error: No top_p value provided. Please provide a value between 0.0 and 1.0."

    async def handle_unknown_command(self, bot, text):
        return "Unknown command. Use `help` for a list of available commands."
