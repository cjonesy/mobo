import os
import requests



class MoboConfig:
    def __init__(
        self,
        model,
        discord_token,
        open_ai_key,
        personality=None,
        personality_url=None,
        temperature=None,
        top_p=None,
        max_history_length=30,
        max_bot_responses=5,
        log_level="INFO",
    ):
        self.model = model
        self.max_history_length = int(max_history_length)
        self.max_bot_responses = int(max_bot_responses)
        self.discord_token = discord_token
        self.open_ai_key = open_ai_key
        self.personality_url = personality_url
        self.temperature = float(temperature) if temperature else None
        self.top_p = float(top_p) if top_p else None
        self.log_level = log_level

        if personality:
          self.personality = personality
        else:
          self.personality = self.personality_from_url()

        if self.temperature and self.top_p:
            raise ValueError("Both temperature and top_p cannot be set")

    def personality_from_url(self):
      response = requests.get(self.personality_url)
      if response.status_code == 200:
          return response.text
      else:
          raise Exception("Failed to load personality")

    @classmethod
    def from_env(cls):
        model = os.environ.get("MOBO_MODEL", "gpt-4")
        max_history_length = os.environ.get("MOBO_MAX_HISTORY_LENGTH", 30)
        max_bot_responses = os.environ.get("MOBO_MAX_BOT_RESPONSES", 5)
        personality_url = os.environ.get("MOBO_PERSONALITY_URL")
        discord_token = os.environ.get("DISCORD_API_KEY")
        open_ai_key = os.environ.get("OPENAI_API_KEY")
        temperature = os.environ.get("MOBO_TEMPERATURE", None)
        top_p = os.environ.get("MOBO_TOP_P", None)
        log_level = os.environ.get("MOBO_LOG_LEVEL", "INFO")

        return cls(
            model=model,
            max_history_length=max_history_length,
            max_bot_responses=max_bot_responses,
            personality_url=personality_url,
            discord_token=discord_token,
            open_ai_key=open_ai_key,
            log_level=log_level,
            temperature=temperature,
            top_p=top_p,
        )
