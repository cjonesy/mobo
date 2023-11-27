from .base_handler import BaseHandler

class AdminCommandHandler(BaseHandler):

    async def handle(self, message, bot):
        response = ""
        parts = message.content.split(' ', 3)
        admin_command = parts[2] if len(parts) > 2 else None
        text = parts[3] if len(parts) > 3 else None

        if admin_command == "help":
            response = "\n".join([
                "Available commands:",
                "`get-personality` - Returns the current personality text",
                "`set-personality <text>` - Changes the bot's personality text",
                "`reset-personality` - Changes the bot's personality back to the default",
                "`get-model` - Returns the current model",
                "`set-model <text>` - Chages the bot's model",
            ])
        elif admin_command == "get-personality":
            response = f"```\n{bot.config.personality}\n```"
        elif admin_command == "set-personality":
            if text:
                bot.config.personality = text
                response = "Personality set."
            else:
                response = "Error: No personality text provided"
        elif admin_command == "reset-personality":
            bot.config.personality = bot.config.personality_from_url()
            response = "Personality reset."
        elif admin_command == "get-model":
            response = f"`{bot.config.model}`"
        elif admin_command == "set-model":
            if text:
                bot.config.model = text
                response = f"Model set to {text}."
            else:
                response = "Error: No model text provided"

        await message.reply(response)