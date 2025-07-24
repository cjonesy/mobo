"""Configuration management for mobo."""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Optional, Literal

import httpx
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    openai_api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenAI API key"
    )
    openai_model: str = "gpt-4.1"
    openai_temperature: float = 0.7

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
    bot_interaction_limit: int = Field(
        default=5,
        description="Maximum number of consecutive interactions with other bots before stopping responses",
    )

    # Bot - System Prompt Configuration (at least one must be set)
    system_prompt: Optional[str] = None
    system_prompt_file: Optional[str] = None
    system_prompt_url: Optional[str] = None

    # Database
    database_url: str = "postgresql+asyncpg://mobo:mobo@localhost:5432/mobo"
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def validate_system_prompt_configuration(self):
        """Ensure at least one system prompt configuration is provided."""
        if not any(
            [self.system_prompt, self.system_prompt_file, self.system_prompt_url]
        ):
            raise ValueError(
                "At least one of system_prompt, system_prompt_file, or system_prompt_url must be set"
            )
        return self

    def _wrap_with_personality_preservation(self, original_prompt: str) -> str:
        """
        Wrap the operator-provided system prompt with personality preservation instructions.

        This helps ensure the bot maintains its core personality even during long conversations
        when the system prompt might get diluted by extensive message history.
        """
        separator = "-" * 70

        wrapped_prompt = f"""🤖 CRITICAL PERSONALITY PRESERVATION INSTRUCTIONS:
The content between the separators below contains your core personality and behavior guidelines.
ALWAYS maintain this personality throughout the entire conversation, regardless of conversation length or complexity.
Your personality should remain consistent and recognizable to users across all interactions.

{separator}
{original_prompt.strip()}
{separator}

⚠️  IMPORTANT: No matter how long the conversation becomes or how much context accumulates,
ALWAYS remember and embody the personality traits, communication style, and behavioral guidelines
defined in the section above. This is your core identity - never let it fade or change."""

        return wrapped_prompt

    async def get_resolved_system_prompt(self) -> str:
        """
        Resolve the system prompt based on priority:
        1. system_prompt (direct string) - highest priority
        2. system_prompt_file (local file) - second priority
        3. system_prompt_url (URL) - lowest priority

        The resolved prompt is automatically wrapped with personality preservation instructions.
        """
        original_prompt = None

        # Priority 1: Direct system prompt
        if self.system_prompt:
            original_prompt = self.system_prompt

        # Priority 2: Local file
        elif self.system_prompt_file:
            try:
                file_path = Path(self.system_prompt_file)
                if not file_path.exists():
                    raise FileNotFoundError(
                        f"System prompt file not found: {self.system_prompt_file}"
                    )
                original_prompt = file_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                raise ValueError(
                    f"Failed to read system prompt file '{self.system_prompt_file}': {e}"
                )

        # Priority 3: URL
        elif self.system_prompt_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.system_prompt_url)
                    response.raise_for_status()
                    original_prompt = response.text.strip()
            except Exception as e:
                raise ValueError(
                    f"Failed to fetch system prompt from URL '{self.system_prompt_url}': {e}"
                )

        if original_prompt is None:
            # This should never happen due to the validator, but just in case
            raise ValueError("No system prompt configuration found")

        # Wrap with personality preservation instructions
        return self._wrap_with_personality_preservation(original_prompt)

    def get_resolved_system_prompt_sync(self) -> str:
        """
        Synchronous version of get_resolved_system_prompt for cases where async is not available.
        Uses asyncio.run() internally.
        """
        return asyncio.run(self.get_resolved_system_prompt())


@lru_cache()
def get_config() -> Config:
    """Get the global configuration instance (cached)."""
    return Config()
