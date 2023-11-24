import os
import discord
import random
import requests
from openai import OpenAI

open_ai_client = OpenAI()
intents = discord.Intents.all()
discord_client = discord.Client(intents=intents)

def get_personality():
    response = requests.get(os.environ.get('PERSONALITY_URL'))

    if response.status_code == 200:
        gist_content = response.text
        return gist_content
    else:
        raise Exception

# Set the response chance (e.g., 20% chance to respond when not mentioned)
RESPONSE_CHANCE_PERCENT = 30
PERSONALITY = get_personality()

@discord_client.event
async def on_ready():
    print(f'We have logged in as {discord_client.user}')

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user:
        return

    # Check if bot is mentioned in the message
    if discord_client.user in message.mentions:
        should_respond = True
    else:
        # Use the configurable chance for the bot to respond when not mentioned
        should_respond = random.randint(1, 100) <= RESPONSE_CHANCE_PERCENT

    if should_respond:
        async with message.channel.typing():  # Show typing indicator while processing
            response = open_ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": PERSONALITY},
                {"role": "user", "content": message.content}]
            )

        await message.channel.send(response.choices[0].message.content)

discord_client.run(token=os.environ.get('DISCORD_API_KEY'))
