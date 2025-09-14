"""
Base models and utilities for the mobo database schema.

This module contains shared mixins, utility functions, and common
database functionality used across all model modules.
"""

from datetime import datetime, UTC

from sqlalchemy import Column, DateTime


class TimestampMixin:
    """Mixin for adding created_at and updated_at timestamps."""

    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
