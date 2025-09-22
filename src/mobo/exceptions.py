"""
Exceptions for the mobo bot.

This module defines custom exceptions used throughout the application.
"""

from datetime import datetime, UTC


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, resource: str, limit: int, reset_time: datetime):
        self.resource = resource
        self.limit = limit
        self.reset_time = reset_time

        now = datetime.now(UTC)
        reset_delta = reset_time - now
        reset_seconds = max(0, int(reset_delta.total_seconds()))

        super().__init__(
            f"Rate limit exceeded for '{resource}'. Limit: {limit}. "
            f"Resets in {reset_seconds} seconds."
        )
