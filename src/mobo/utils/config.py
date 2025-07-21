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
    openai_model: str = "gpt-4o-mini"
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

    # Bot - System Prompt Configuration (at least one must be set)
    system_prompt: Optional[str] = None
    system_prompt_file: Optional[str] = None
    system_prompt_url: Optional[str] = None

    # Database
    database_url: str = "postgresql+asyncpg://mobo:mobo@localhost:5432/mobo"
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

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

    async def get_resolved_system_prompt(self) -> str:
        """
        Resolve the system prompt based on priority:
        1. system_prompt (direct string) - highest priority
        2. system_prompt_file (local file) - second priority
        3. system_prompt_url (URL) - lowest priority
        """
        # Priority 1: Direct system prompt
        if self.system_prompt:
            return self.system_prompt

        # Priority 2: Local file
        if self.system_prompt_file:
            try:
                file_path = Path(self.system_prompt_file)
                if not file_path.exists():
                    raise FileNotFoundError(
                        f"System prompt file not found: {self.system_prompt_file}"
                    )
                return file_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                raise ValueError(
                    f"Failed to read system prompt file '{self.system_prompt_file}': {e}"
                )

        # Priority 3: URL
        if self.system_prompt_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.system_prompt_url)
                    response.raise_for_status()
                    return response.text.strip()
            except Exception as e:
                raise ValueError(
                    f"Failed to fetch system prompt from URL '{self.system_prompt_url}': {e}"
                )

        # This should never happen due to the validator, but just in case
        raise ValueError("No system prompt configuration found")

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
