"""
Configuration management for the Discord bot.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from functools import lru_cache
from typing import Literal, List, Any

from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordSettings(BaseSettings):
    """Discord-specific configuration settings."""

    token: SecretStr = Field(
        default=SecretStr(""),
        description="Discord bot token from Discord Developer Portal",
    )


class OpenRouterSettings(BaseSettings):
    """OpenRouter LLM service configuration settings."""

    api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenRouter API key for LLM access"
    )
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API requests",
    )


class SupervisorLLMSettings(BaseSettings):
    """Supervisor LLM configuration for tool planning and orchestration."""

    model: str = Field(
        default="openai/gpt-5-mini",
        description="Model for supervisor (tool planning) - needs tool calling",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Temperature for supervisor decisions",
    )


class ResponseLLMSettings(BaseSettings):
    """Response generation LLM configuration for personality and creativity."""

    model: str = Field(
        default="openai/gpt-4.1",
        description="Model for creative response generation with personality",
    )
    temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        description="Temperature for creative response generation",
    )


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: str = Field(
        default="postgresql+asyncpg://mobo:mobo@localhost:5432/mobo",
        description="PostgreSQL database connection URL (used by LangGraph PostgresSaver and PostgresStore)",
    )
    echo: bool = Field(
        default=False, description="Enable SQL query logging (useful for debugging)"
    )
    pool_size: int = Field(
        default=10, ge=1, le=50, description="Database connection pool size"
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum database connection pool overflow",
    )

    @field_validator("url")
    def validate_database_url(cls, v):
        """Ensure database URL is PostgreSQL."""
        if not v.startswith("postgresql"):
            raise ValueError("Database URL must be PostgreSQL")
        return v

    @property
    def url_for_langgraph(self) -> str:
        """Get database URL in format expected by LangGraph (psycopg format)."""
        # LangGraph PostgreSQL connectors use psycopg, not SQLAlchemy
        if self.url.startswith("postgresql+asyncpg://"):
            return self.url.replace("postgresql+asyncpg://", "postgresql://")
        return self.url

    @property
    def url_for_sqlalchemy(self) -> str:
        """Get database URL in format expected by SQLAlchemy (with async driver)."""
        # Ensure we have the async driver for SQLAlchemy
        if self.url.startswith("postgresql://"):
            return self.url.replace("postgresql://", "postgresql+asyncpg://")
        return self.url


class OpenAISettings(BaseSettings):
    """OpenAI API configuration for embeddings and image generation."""

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API key for DALL-E image generation and embeddings",
    )


class PersonalitySettings(BaseSettings):
    """Bot personality and behavior configuration."""

    prompt: str = Field(
        default="",
        description="LLM personality prompt - supports multiline text or base64 encoded",
    )

    @field_validator("prompt")
    def decode_personality_prompt(cls, v):
        """Auto-decode base64 if the prompt appears to be encoded."""
        if not v:
            return v

        try:
            import base64

            decoded = base64.b64decode(v).decode("utf-8")
            print(f"🔓 Auto-decoded base64 personality prompt ({len(decoded)} chars)")
            return decoded
        except Exception as e:
            print(f"⚠️  Failed to decode base64 personality prompt: {e}")
            # Fall through to return original value

        return v


class ImageGenerationSettings(BaseSettings):
    """Image generation configuration for DALL-E."""

    model: Literal["dall-e-2", "dall-e-3"] = Field(
        default="dall-e-3", description="DALL-E model for image generation"
    )
    size: Literal[
        "256x256",
        "512x512",
        "1024x1024",  # dall-e-2
        "1536x1024",
        "1024x1536",
        "1792x1024",
        "1024x1792",  # dall-e-3
    ] = Field(default="1024x1024", description="Generated image dimensions")
    quality: Literal["standard", "hd"] = Field(
        default="standard", description="Image quality (dall-e-3 only)"
    )


class GiphySettings(BaseSettings):
    """Giphy API configuration for GIF search."""

    api_key: SecretStr = Field(
        default=SecretStr(""), description="Giphy API key for GIF search"
    )


class GoogleSearchSettings(BaseSettings):
    """Google Custom Search API configuration for web search."""

    api_key: SecretStr = Field(
        default=SecretStr(""), description="Google Custom Search API key"
    )
    cse_id: str = Field(default="", description="Google Custom Search Engine ID")


class MemorySettings(BaseSettings):
    """Memory and RAG (Retrieval-Augmented Generation) configuration."""

    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for RAG context retrieval (0.0-1.0)",
    )
    recent_messages_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of recent messages to include in context",
    )
    relevant_messages_limit: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of semantically relevant messages to include in context",
    )


class BotInteractionSettings(BaseSettings):
    """Bot interaction limits and anti-loop protection configuration."""

    max_bot_responses: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Maximum number of responses to other bots before stopping (0 = unlimited)",
    )
    bot_response_cooldown_seconds: int = Field(
        default=60,
        ge=0,
        le=3600,
        description="Seconds to wait after hitting bot response limit before responding again (0 = no cooldown)",
    )


class AdminSettings(BaseSettings):
    """Admin user configuration."""

    user_ids: List[str] = Field(
        default_factory=list, description="Discord user IDs with admin privileges"
    )

    @field_validator("user_ids", mode="before")
    def parse_admin_user_ids(cls, v):
        """Parse admin user IDs from comma-separated string or list."""
        if isinstance(v, str):
            return [id.strip() for id in v.split(",") if id.strip()]
        elif isinstance(v, (int, float)):
            return [str(int(v))]
        elif isinstance(v, list):
            return [str(id) for id in v]
        return v


class Settings(BaseSettings):
    """Main configuration class for the Discord bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
        env_prefix="MOBO_",
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize settings, allowing environment variables to provide required fields."""
        super().__init__(**kwargs)

    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    supervisor_llm: SupervisorLLMSettings = Field(default_factory=SupervisorLLMSettings)
    response_llm: ResponseLLMSettings = Field(default_factory=ResponseLLMSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    personality: PersonalitySettings = Field(default_factory=PersonalitySettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    bot_interaction: BotInteractionSettings = Field(
        default_factory=BotInteractionSettings
    )
    admin: AdminSettings = Field(default_factory=AdminSettings)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    debug_mode: bool = Field(
        default=False, description="Enable debug features and verbose logging"
    )

    # Tools
    image_generation: ImageGenerationSettings = Field(
        default_factory=ImageGenerationSettings
    )
    giphy: GiphySettings = Field(default_factory=GiphySettings)
    google_search: GoogleSearchSettings = Field(default_factory=GoogleSearchSettings)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
