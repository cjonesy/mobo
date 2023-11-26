import os
import discord
import requests
from openai import OpenAI

open_ai_client = OpenAI()
intents = discord.Intents.all()
discord_client = discord.Client(intents=intents)

def load_personality():
    response = requests.get(os.environ.get('PERSONALITY_URL'))
    if response.status_code == 200:
        return response.text
    else:
        raise Exception

def admin(message):
    response = ""
    parts = message.content.split(' ', 2)

    admin_command = parts[1] if len(parts) > 1 else None
    text = parts[2] if len(parts) > 2 else None

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
        response = f"```\n{PERSONALITY}\n```"
    elif admin_command == "set-personality":
        if text:
            PERSONALITY = text
            response = "Personality set."
        else:
            response = "Error: No personality text provided"
    elif admin_command == "reset-personality":
        load_personality()
        response = "Personality reset."
    elif admin_command == "get-model":
        response = f"`{MODEL}`"
    elif admin_command == "set-model":
        if text:
            MODEL = text
            response = f"Model set to {text}."
        else:
            response = "Error: No model text provided"
    message.reply(response)

MODEL="gpt-3.5-turbo"
PERSONALITY = load_personality()
MAX_HISTORY_LENGTH = 30 # Limit the size of the conversation history
conversation_histories = {}  # Dictionary to store conversation history

@discord_client.event
async def on_ready():
    print(f'We have logged in as {discord_client.user}')

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user:
        return

    if message.content.startswith("!admin "):
        admin(message)
        return

    channel_id = str(message.channel.id)
    if channel_id not in conversation_histories:
        conversation_histories[channel_id] = []

    if discord_client.user.mentioned_in(message):
        # Add user message to conversation history
        conversation_histories[channel_id].append({"role": "user", "content": message.content})

        async with message.channel.typing():
            response = open_ai_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": PERSONALITY}
                ] + conversation_histories[channel_id]
            )

        bot_response = response.choices[0].message.content
        await message.reply(bot_response)

        # Add bot response to conversation history
        conversation_histories[channel_id].append({"role": "assistant", "content": bot_response})

        conversation_histories[channel_id] = conversation_histories[channel_id][-MAX_HISTORY_LENGTH:]

discord_client.run(token=os.environ.get('DISCORD_API_KEY'))
