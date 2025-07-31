"""Configuration management for the LangGraph Discord bot."""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Optional, Literal

import httpx
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Main configuration class for LangGraph Discord bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI Configuration
    openai_api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenAI API key"
    )
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.7
    embedding_model: str = "text-embedding-3-small"

    # Image Generation
    image_model: str = "dall-e-3"
    image_size: Literal[
        "1024x1024", "1536x1024", "1024x1536", "1792x1024", "1024x1792"
    ] = "1024x1024"
    image_quality: Literal["standard", "hd"] = "standard"
    image_daily_limit: int = 20
    image_hourly_limit: int = 2

    # Discord
    discord_token: SecretStr = Field(
        default=SecretStr(""), description="Discord bot token"
    )

    # Bot Behavior
    max_bot_responses: int = Field(
        default=3,
        description="Maximum number of consecutive interactions with other bots before stopping responses",
    )
    top_k_memory_results: int = Field(
        default=5,
        description="Number of similar past messages to retrieve for context",
    )
    max_context_messages: int = Field(
        default=5,
        description="Maximum number of recent conversation messages to include in context",
    )

    # Personality Configuration (at least one must be set)
    personality_prompt: Optional[str] = None
    personality_prompt_file: Optional[str] = Field(
        default=None, description="Path to personality prompt file"
    )
    personality_prompt_url: Optional[str] = None

    # Database
    database_url: str = "postgresql+asyncpg://mobo:mobo@localhost:5432/mobo"
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def validate_personality_configuration(self) -> "Config":
        """Ensure at least one personality prompt configuration is provided."""
        if not any(
            [
                self.personality_prompt,
                self.personality_prompt_file,
                self.personality_prompt_url,
            ]
        ):
            raise ValueError(
                "At least one of personality_prompt, personality_prompt_file, or personality_prompt_url must be set"
            )
        return self

    def _wrap_with_personality_preservation(self, original_prompt: str) -> str:
        """Wrap the operator-provided personality prompt with preservation instructions."""
        wrapped_prompt: str = f"""IMPORTANT: Maintain the personality and behavior defined below throughout the entire conversation.

{original_prompt.strip()}

Stay consistent with your defined personality regardless of conversation length."""

        return wrapped_prompt

    async def get_resolved_personality_prompt(self) -> str:
        """
        Resolve the personality prompt based on priority:
        1. personality_prompt (direct string) - highest priority
        2. personality_prompt_file (local file) - second priority
        3. personality_prompt_url (URL) - lowest priority
        """
        original_prompt: Optional[str] = None

        # Priority 1: Direct personality prompt
        if self.personality_prompt:
            original_prompt = self.personality_prompt

        # Priority 2: Local file
        elif self.personality_prompt_file:
            try:
                file_path: Path = Path(self.personality_prompt_file)
                if not file_path.exists():
                    raise FileNotFoundError(
                        f"Personality prompt file not found: {self.personality_prompt_file}"
                    )
                original_prompt = file_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                raise ValueError(
                    f"Failed to read personality prompt file '{self.personality_prompt_file}': {e}"
                )

        # Priority 3: URL
        elif self.personality_prompt_url:
            try:
                async with httpx.AsyncClient() as client:
                    response: httpx.Response = await client.get(
                        self.personality_prompt_url
                    )
                    response.raise_for_status()
                    original_prompt = response.text.strip()
            except Exception as e:
                raise ValueError(
                    f"Failed to fetch personality prompt from URL '{self.personality_prompt_url}': {e}"
                )

        if original_prompt is None:
            # This should never happen due to the validator, but just in case
            raise ValueError("No personality prompt configuration found")

        # Wrap with personality preservation instructions
        return self._wrap_with_personality_preservation(original_prompt)

    def get_resolved_personality_prompt_sync(self) -> str:
        """Synchronous version of get_resolved_personality_prompt."""
        return asyncio.run(self.get_resolved_personality_prompt())


@lru_cache()
def get_config() -> Config:
    """Get the global configuration instance (cached)."""
    return Config()
