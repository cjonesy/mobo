"""
Configuration management for the Discord bot.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from functools import lru_cache
from typing import Literal, List, Any

from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from .utils.text_encoding import decode_base64_if_encoded


class DiscordSettings(BaseSettings):
    """Discord-specific configuration settings."""

    token: SecretStr = Field(
        default=SecretStr(""),
        description="Discord bot token from Discord Developer Portal",
    )

    @field_validator("token")
    def validate_discord_token(cls, v):
        """Ensure Discord token is set to a real value."""
        token_value = v.get_secret_value() if isinstance(v, SecretStr) else str(v)

        if not token_value or token_value.strip() == "":
            raise ValueError(
                "Discord bot token must be set. Please configure MOBO_DISCORD__TOKEN environment variable."
            )

        # Basic Discord token format validation (they start with a bot ID, then a dot, then the token)
        if len(token_value) < 50:  # Discord tokens are typically much longer
            raise ValueError(
                "Discord bot token appears to be invalid (too short). Please check your token."
            )

        return v


class OpenRouterSettings(BaseSettings):
    """OpenRouter LLM service configuration settings."""

    api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenRouter API key for LLM access"
    )
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API requests",
    )

    @field_validator("api_key")
    def validate_openrouter_api_key(cls, v):
        """Ensure OpenRouter API key is set to a real value."""
        api_key_value = v.get_secret_value() if isinstance(v, SecretStr) else str(v)

        if not api_key_value or api_key_value.strip() == "":
            raise ValueError(
                "OpenRouter API key must be set. Please configure MOBO_OPENROUTER__API_KEY environment variable."
            )

        # Basic API key format validation - OpenRouter keys typically start with "sk-or-"
        if len(api_key_value) < 20:  # API keys are typically much longer
            raise ValueError(
                "OpenRouter API key appears to be invalid (too short). Please check your key."
            )

        return v


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


class SummarizationLLMSettings(BaseSettings):
    """Summarization LLM configuration for web content analysis."""

    model: str = Field(
        default="anthropic/claude-3-haiku",
        description="Model for web content summarization and analysis",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for content summarization (lower for consistency)",
    )
    max_chars: int = Field(
        default=50000,
        ge=1000,
        le=150000,
        description="Maximum characters of extracted text to send to LLM for summarization (consider model context limits)",
    )


class VisionLLMSettings(BaseSettings):
    """Vision LLM configuration for image analysis."""

    model: str = Field(
        default="openai/gpt-4o",
        description="Model for image analysis and vision tasks (must support vision)",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for vision analysis (lower for consistency)",
    )


class ContextLearningLLMSettings(BaseSettings):
    """Context learning LLM configuration for analyzing user interaction patterns."""

    model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for analyzing conversation patterns and learning user context (fast, cheap model recommended)",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for context analysis (lower for consistent analysis)",
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
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI API requests",
    )

    @field_validator("api_key")
    def validate_openai_api_key(cls, v):
        """Ensure OpenAI API key is set to a real value."""
        api_key_value = v.get_secret_value() if isinstance(v, SecretStr) else str(v)

        if not api_key_value or api_key_value.strip() == "":
            raise ValueError(
                "OpenAI API key must be set. Please configure MOBO_OPENAI__API_KEY environment variable."
            )

        # Basic API key format validation - OpenAI keys typically start with "sk-"
        if not api_key_value.startswith("sk-") or len(api_key_value) < 40:
            raise ValueError(
                "OpenAI API key appears to be invalid. Please check your key format and length."
            )

        return v


class PersonalitySettings(BaseSettings):
    """Bot personality and behavior configuration."""

    prompt: str = Field(
        default="",
        description="LLM personality prompt - supports multiline text or base64 encoded",
    )

    @field_validator("prompt")
    def decode_personality_prompt(cls, v):
        """Auto-decode base64 if the prompt appears to be encoded and ensure it's not empty."""
        decoded_prompt = decode_base64_if_encoded(v)

        if not decoded_prompt or decoded_prompt.strip() == "":
            raise ValueError(
                "Personality prompt must be set. Please configure MOBO_PERSONALITY__PROMPT environment variable."
            )

        return decoded_prompt


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

    @field_validator("api_key")
    def validate_giphy_api_key(cls, v):
        """Ensure Giphy API key is set to a real value."""
        api_key_value = v.get_secret_value() if isinstance(v, SecretStr) else str(v)

        if not api_key_value or api_key_value.strip() == "":
            raise ValueError(
                "Giphy API key must be set. Please configure MOBO_GIPHY__API_KEY environment variable."
            )

        # Basic API key format validation - Giphy keys are typically alphanumeric and 32 characters
        if len(api_key_value) < 20:  # API keys are typically much longer
            raise ValueError(
                "Giphy API key appears to be invalid (too short). Please check your key."
            )

        return v


class GoogleSearchSettings(BaseSettings):
    """Google Custom Search API configuration for web search."""

    api_key: SecretStr = Field(
        default=SecretStr(""), description="Google Custom Search API key"
    )
    cse_id: str = Field(default="", description="Google Custom Search Engine ID")

    @field_validator("api_key")
    def validate_google_api_key(cls, v):
        """Ensure Google API key is set to a real value."""
        api_key_value = v.get_secret_value() if isinstance(v, SecretStr) else str(v)

        if not api_key_value or api_key_value.strip() == "":
            raise ValueError(
                "Google Custom Search API key must be set. Please configure MOBO_GOOGLE_SEARCH__API_KEY environment variable."
            )

        # Basic API key format validation - Google API keys are typically 39 characters
        if len(api_key_value) < 30:  # API keys are typically much longer
            raise ValueError(
                "Google Custom Search API key appears to be invalid (too short). Please check your key."
            )

        return v

    @field_validator("cse_id")
    def validate_google_cse_id(cls, v):
        """Ensure Google Custom Search Engine ID is set to a real value."""
        if not v or v.strip() == "":
            raise ValueError(
                "Google Custom Search Engine ID must be set. Please configure MOBO_GOOGLE_SEARCH__CSE_ID environment variable."
            )

        # Basic CSE ID format validation - Google CSE IDs are typically alphanumeric with colons
        if len(v) < 10:  # CSE IDs are typically much longer
            raise ValueError(
                "Google Custom Search Engine ID appears to be invalid (too short). Please check your CSE ID."
            )

        return v


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
        default=600,
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
    summarization_llm: SummarizationLLMSettings = Field(
        default_factory=SummarizationLLMSettings
    )
    vision_llm: VisionLLMSettings = Field(default_factory=VisionLLMSettings)
    context_learning_llm: ContextLearningLLMSettings = Field(
        default_factory=ContextLearningLLMSettings
    )
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


settings = get_settings()
