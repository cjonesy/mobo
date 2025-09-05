"""
Configuration management for the Discord bot.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from functools import lru_cache
from typing import Literal, List

from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main configuration class for the Discord bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =============================================================================
    # DISCORD CONFIGURATION
    # =============================================================================
    discord_token: SecretStr = Field(
        description="Discord bot token from Discord Developer Portal"
    )

    # =============================================================================
    # OPENROUTER / LLM CONFIGURATION
    # =============================================================================
    openrouter_api_key: SecretStr = Field(
        description="OpenRouter API key for LLM access"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenRouter API requests",
    )

    # Supervisor LLM (needs tool calling capabilities - can be smaller/cheaper)
    chatbot_model: str = Field(
        default="openai/gpt-5-mini",
        description="Model for supervisor (tool planning) - needs tool calling",
    )
    chatbot_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Temperature for supervisor decisions",
    )

    # Response generation LLM (for personality and creativity)
    response_model: str = Field(
        default="openai/gpt-4.1",
        description="Model for creative response generation with personality",
    )
    response_temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        description="Temperature for creative response generation",
    )

    # =============================================================================
    # PERSONALITY CONFIGURATION
    # =============================================================================
    personality_prompt: str = Field(
        description="LLM personality prompt - supports multiline text or base64 encoded"
    )

    @field_validator("personality_prompt")
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

    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    database_url: str = Field(
        default="postgresql+asyncpg://mobo:mobo@localhost:5432/mobo",
        description="PostgreSQL database connection URL (used by LangGraph PostgresSaver and PostgresStore)",
    )
    database_echo: bool = Field(
        default=False, description="Enable SQL query logging (useful for debugging)"
    )
    database_pool_size: int = Field(
        default=10, ge=1, le=50, description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum database connection pool overflow",
    )

    @field_validator("database_url")
    def validate_database_url(cls, v):
        """Ensure database URL is PostgreSQL and convert from SQLAlchemy format to psycopg format."""
        if not v.startswith("postgresql"):
            raise ValueError("Database URL must be PostgreSQL")

        # Convert SQLAlchemy format (postgresql+asyncpg://) to psycopg format (postgresql://)
        # LangGraph PostgreSQL connectors use psycopg, not SQLAlchemy
        if v.startswith("postgresql+asyncpg://"):
            v = v.replace("postgresql+asyncpg://", "postgresql://")
            print(f"🔄 Converted SQLAlchemy format to psycopg format: {v}")

        return v

    # =============================================================================
    # BOT BEHAVIOR CONFIGURATION
    # =============================================================================
    max_bot_responses: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum consecutive responses to other bots before stopping",
    )

    # LangGraph manages conversation history automatically - no manual configuration needed

    # =============================================================================
    # EXTERNAL API CONFIGURATION
    # =============================================================================

    # OpenAI (for image generation)
    openai_api_key: SecretStr = Field(
        default=SecretStr(""), description="OpenAI API key for DALL-E image generation"
    )
    image_model: Literal["dall-e-2", "dall-e-3"] = Field(
        default="dall-e-3", description="DALL-E model for image generation"
    )
    image_size: Literal[
        "256x256",
        "512x512",
        "1024x1024",  # dall-e-2
        "1536x1024",
        "1024x1536",
        "1792x1024",
        "1024x1792",  # dall-e-3
    ] = Field(default="1024x1024", description="Generated image dimensions")
    image_quality: Literal["standard", "hd"] = Field(
        default="standard", description="Image quality (dall-e-3 only)"
    )

    # Giphy
    giphy_api_key: SecretStr = Field(
        default=SecretStr(""), description="Giphy API key for GIF search"
    )

    # Google Custom Search
    google_custom_search_api_key: SecretStr = Field(
        default=SecretStr(""), description="Google Custom Search API key"
    )
    google_cse_id: str = Field(default="", description="Google Custom Search Engine ID")

    # =============================================================================
    # ADMIN AND DEVELOPMENT
    # =============================================================================
    admin_user_ids: List[str] = Field(
        default_factory=list, description="Discord user IDs with admin privileges"
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    debug_mode: bool = Field(
        default=False, description="Enable debug features and verbose logging"
    )

    @field_validator("admin_user_ids", mode="before")
    def parse_admin_user_ids(cls, v):
        """Parse admin user IDs from comma-separated string or list."""
        if isinstance(v, str):
            return [id.strip() for id in v.split(",") if id.strip()]
        elif isinstance(v, (int, float)):
            return [str(int(v))]
        elif isinstance(v, list):
            return [str(id) for id in v]
        return v

    # =============================================================================
    # VALIDATION AND UTILITY METHODS
    # =============================================================================

    def is_admin(self, user_id: str) -> bool:
        """Check if a user ID has admin privileges."""
        return str(user_id) in self.admin_user_ids

    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return "postgresql" in self.database_url.lower()

    def get_personality_prompt_sync(self) -> str:
        """Get the personality prompt synchronously for validation."""
        return self.personality_prompt

    async def get_personality_prompt(self) -> str:
        """Get the personality prompt asynchronously."""
        return self.personality_prompt

    def get_openai_config(self) -> dict:
        """Get OpenAI configuration for image generation."""
        return {
            "api_key": self.openai_api_key.get_secret_value(),
            "model": self.image_model,
            "size": self.image_size,
            "quality": self.image_quality,
        }

    def get_chatbot_config(self) -> dict:
        """Get main chatbot LLM configuration."""
        return {
            "model": self.chatbot_model,
            "temperature": self.chatbot_temperature,
            "api_key": self.openrouter_api_key.get_secret_value(),
            "base_url": self.openrouter_base_url,
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# =============================================================================
# CONFIGURATION VALIDATION HELPERS
# =============================================================================


def validate_required_settings() -> None:
    """Validate that all required settings are configured."""
    settings = get_settings()
    errors = []

    # Check required tokens
    if not settings.discord_token.get_secret_value():
        errors.append("DISCORD_TOKEN is required")

    if not settings.openrouter_api_key.get_secret_value():
        errors.append("OPENROUTER_API_KEY is required")

    if not settings.openai_api_key.get_secret_value():
        errors.append("OPENAI_API_KEY is required for embeddings and image generation")

    # Check personality configuration
    try:
        settings.get_personality_prompt_sync()
    except ValueError as e:
        errors.append(f"Personality configuration error: {e}")

    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"- {error}" for error in errors)
        )


def print_config_summary() -> None:
    """Print a summary of current configuration (for debugging)."""
    settings = get_settings()

    print("🔧 Configuration Summary:")
    print(
        f"  Discord: {'✅ Configured' if settings.discord_token.get_secret_value() else '❌ Missing token'}"
    )
    print(
        f"  OpenRouter: {'✅ Configured' if settings.openrouter_api_key.get_secret_value() else '❌ Missing key'}"
    )
    print(f"  Database: {settings.database_url}")
    print(f"  Chatbot Model: {settings.chatbot_model}")
    print(f"  Image Model: {settings.image_model}")
    print(f"  Log Level: {settings.log_level}")
    print(f"  Debug Mode: {settings.debug_mode}")
    print(f"  Admin Users: {len(settings.admin_user_ids)} configured")

    # Check optional APIs
    optional_apis = []
    if settings.openai_api_key.get_secret_value():
        optional_apis.append("OpenAI (images)")
    if settings.giphy_api_key.get_secret_value():
        optional_apis.append("Giphy")
    if settings.google_custom_search_api_key.get_secret_value():
        optional_apis.append("Google Custom Search")

    if optional_apis:
        print(f"  Optional APIs: {', '.join(optional_apis)}")
