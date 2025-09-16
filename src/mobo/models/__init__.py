"""
Mobo database models package.

This package contains all SQLAlchemy models organized by functional area:
- base: Common mixins and utilities
- user: User profiles, preferences, and aliases
- bot_interaction: Bot interaction tracking for anti-loop protection
- analytics: Conversation and usage analytics
- rate_limit: API rate limiting and usage tracking
"""

from mobo.models.base import (
    TimestampMixin,
)

from mobo.models.user import (
    User,
    UserLike,
    UserDislike,
    UserAlias,
)

from mobo.models.bot_interaction import (
    BotInteraction,
)

from mobo.models.rate_limit import (
    RateLimit,
)

__all__ = [
    # Base utilities
    "TimestampMixin",
    # User models
    "User",
    "UserLike",
    "UserDislike",
    "UserAlias",
    # Bot interaction models
    "BotInteraction",
    # Rate limiting models
    "RateLimit",
]
