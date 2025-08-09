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

    openai_api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenAI API key"
    )
    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenRouter API key"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API requests",
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI API requests",
    )
    openai_model: str = "openai/gpt-4.1"
    openai_temperature: float = 1.0
    rag_model: str = Field(
        default="openai/gpt-5-mini",
        description="Model for RAG query analysis (cheaper/faster model recommended)",
    )
    user_profile_model: str = Field(
        default="openai/gpt-5-mini",
        description="Model for user profile analysis (cheaper/faster model recommended)",
    )
    embedding_model: str = "text-embedding-3-small"

    # Giphy Configuration
    giphy_api_key: SecretStr = Field(default=SecretStr(""), description="Giphy API key")

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
    admin_user_ids: list[str] = Field(
        default_factory=lambda: [],
        description="List of Discord user IDs that can use admin commands. Set via ADMIN_USER_IDS env var as comma-separated values",
    )

    @model_validator(mode="before")
    def parse_admin_user_ids(cls, values: dict) -> dict:
        """Parse admin user IDs from environment variable."""
        if admin_ids := values.get("admin_user_ids"):
            # Handle string input (comma-separated)
            if isinstance(admin_ids, str):
                values["admin_user_ids"] = [
                    id.strip() for id in admin_ids.split(",") if id.strip()
                ]
            # Handle single integer input
            elif isinstance(admin_ids, int):
                values["admin_user_ids"] = [str(admin_ids)]
            # Handle single float input (some env vars might convert large ints to float)
            elif isinstance(admin_ids, float) and admin_ids.is_integer():
                values["admin_user_ids"] = [str(int(admin_ids))]
        return values

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
        default=10,
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
    verbose_logging: bool = Field(
        default=False,
        description="Enable verbose logging for LangChain agent execution",
    )

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

        return original_prompt

    def get_resolved_personality_prompt_sync(self) -> str:
        """Synchronous version of get_resolved_personality_prompt."""
        return asyncio.run(self.get_resolved_personality_prompt())


@lru_cache()
def get_config() -> Config:
    """Get the global configuration instance (cached)."""
    return Config()
