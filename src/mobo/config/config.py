import os
import requests
import time
from datetime import datetime


class MoboConfig:
    def __init__(
        self,
        model,
        discord_token,
        open_ai_key,
        personality=None,
        personality_url=None,
        temperature=0.5,
        max_history_length=300,
        max_bot_responses=5,
        max_daily_images=10,
        enable_image_generation=False,
        image_model="dall-e-3",
        image_size="1024x1024",
        log_level="INFO",
    ):
        self.model = model
        self.max_history_length = int(max_history_length)
        self.max_bot_responses = int(max_bot_responses)
        self.discord_token = discord_token
        self.open_ai_key = open_ai_key
        self.personality_url = personality_url
        self.temperature = float(temperature)
        self.log_level = log_level

        # Image generation configuration
        self.enable_image_generation = bool(enable_image_generation)
        self.image_model = image_model
        self.image_size = image_size
        self.max_daily_images = int(max_daily_images)
        self.daily_image_count = 0
        self.last_image_reset = datetime.now().date()

        if personality:
            self.personality = personality
        else:
            self.personality = self.personality_from_url()

    def personality_from_url(self):
        response = requests.get(self.personality_url)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception("Failed to load personality")

    def can_generate_image(self):
        # Reset counter if it's a new day
        current_date = datetime.now().date()
        if current_date > self.last_image_reset:
            self.daily_image_count = 0
            self.last_image_reset = current_date

        # Check if image generation is enabled and within daily limit
        return (
            self.enable_image_generation
            and self.daily_image_count < self.max_daily_images
        )

    def increment_image_count(self):
        # Reset counter if it's a new day
        current_date = datetime.now().date()
        if current_date > self.last_image_reset:
            self.daily_image_count = 0
            self.last_image_reset = current_date

        self.daily_image_count += 1
        return self.daily_image_count

    @classmethod
    def from_env(cls):
        model = os.environ.get("MOBO_MODEL", "gpt-4")
        max_history_length = os.environ.get("MOBO_MAX_HISTORY_LENGTH", 300)
        max_bot_responses = os.environ.get("MOBO_MAX_BOT_RESPONSES", 5)
        personality_url = os.environ.get("MOBO_PERSONALITY_URL")
        discord_token = os.environ.get("DISCORD_API_KEY")
        open_ai_key = os.environ.get("OPENAI_API_KEY")
        temperature = os.environ.get("MOBO_TEMPERATURE", 0.5)
        log_level = os.environ.get("MOBO_LOG_LEVEL", "INFO")

        # Image generation config from environment variables
        enable_image_generation = os.environ.get("MOBO_ENABLE_IMAGE_GENERATION", False)
        max_daily_images = os.environ.get("MOBO_MAX_DAILY_IMAGES", 10)
        image_model = os.environ.get("MOBO_IMAGE_MODEL", "dall-e-3")
        image_size = os.environ.get("MOBO_IMAGE_SIZE", "1024x1024")

        return cls(
            model=model,
            max_history_length=max_history_length,
            max_bot_responses=max_bot_responses,
            personality_url=personality_url,
            discord_token=discord_token,
            open_ai_key=open_ai_key,
            log_level=log_level,
            temperature=temperature,
            enable_image_generation=enable_image_generation,
            max_daily_images=max_daily_images,
            image_model=image_model,
            image_size=image_size,
        )
