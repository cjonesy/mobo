"""
Rate limiting models for the mobo bot.

This module defines the database schema for tracking API usage
and implementing rate limiting across different resources.
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Index,
)

from mobo.db import Base
from mobo.models.base import TimestampMixin


class RateLimit(Base, TimestampMixin):
    """
    Tracks API usage for rate limiting across different resources.

    This allows multiple tools to share rate limits for the same underlying
    resource (e.g., multiple tools using Google Search API).
    """

    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True)

    # Resource identification
    resource_name = Column(String, nullable=False, index=True)  # e.g., 'google-search'
    period_start = Column(
        DateTime, nullable=False, index=True
    )  # Start of current period
    period_end = Column(DateTime, nullable=False, index=True)  # End of current period

    # Usage tracking
    current_usage = Column(Integer, nullable=False, default=0)
    max_usage = Column(Integer, nullable=False)  # Maximum allowed in this period

    # Optional user-specific rate limiting
    user_id = Column(String, nullable=True, index=True)  # None for global limits

    # Metadata
    period_type = Column(
        String, nullable=False, default="day"
    )  # 'minute', 'hour', 'day', 'month'

    __table_args__ = (
        Index(
            "idx_rate_limits_resource_period",
            "resource_name",
            "period_start",
            "period_end",
        ),
        Index("idx_rate_limits_resource_user", "resource_name", "user_id"),
        # Unique constraint to prevent duplicate periods
        Index(
            "idx_rate_limits_unique",
            "resource_name",
            "period_start",
            "user_id",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<RateLimit(resource={self.resource_name}, usage={self.current_usage}/{self.max_usage})>"
