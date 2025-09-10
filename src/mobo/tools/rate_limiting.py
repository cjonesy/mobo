"""
Rate limiting functionality for bot tools.

This module provides decorators and utilities for rate limiting API calls
across different resources, with persistent storage in the database.
"""

import logging
from datetime import datetime, UTC
from functools import wraps
from typing import Optional, Callable, Any, Dict, TypeVar, cast
from contextlib import asynccontextmanager

from sqlalchemy import select

from mobo.memory.models import RateLimit
from mobo.db import get_session_maker

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@asynccontextmanager
async def get_rate_limit_session():
    """Get an async database session for rate limiting operations."""
    session_maker = get_session_maker()
    session = session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, resource: str, limit: int, reset_time: datetime):
        self.resource = resource
        self.limit = limit
        self.reset_time = reset_time

        reset_delta = reset_time - datetime.now(UTC)
        reset_seconds = max(0, int(reset_delta.total_seconds()))

        super().__init__(
            f"Rate limit exceeded for '{resource}'. Limit: {limit}. "
            f"Resets in {reset_seconds} seconds."
        )


async def check_and_increment_rate_limit(
    resource: str,
    max_requests: int,
    period_type: str = "day",
    user_id: Optional[str] = None,
    increment: int = 1,
) -> Dict[str, Any]:
    """
    Check if a rate limit allows the request and increment usage.

    Args:
        resource: Name of the resource (e.g., 'google-search')
        max_requests: Maximum requests allowed in the period
        period_type: Type of period ('minute', 'hour', 'day', 'month')
        user_id: Optional user-specific rate limiting
        increment: Number of requests to increment by

    Returns:
        Dictionary with rate limit information

    Raises:
        RateLimitExceeded: If the rate limit would be exceeded
    """
    async with get_rate_limit_session() as session:
        # Get current period bounds
        period_start, period_end = RateLimit.get_period_bounds(period_type)

        # Try to get existing rate limit record
        stmt = select(RateLimit).where(
            RateLimit.resource_name == resource,
            RateLimit.period_start == period_start,
            RateLimit.user_id == user_id,
        )

        result = await session.execute(stmt)
        rate_limit = result.scalar_one_or_none()

        if rate_limit is None:
            # Create new rate limit record
            rate_limit = RateLimit(
                resource_name=resource,
                period_start=period_start,
                period_end=period_end,
                current_usage=0,
                max_usage=max_requests,
                user_id=user_id,
                period_type=period_type,
            )
            session.add(rate_limit)
            await session.flush()  # Get the ID

        # Check if the request would exceed the limit
        if rate_limit.is_exceeded(increment):
            raise RateLimitExceeded(
                resource, rate_limit.max_usage, rate_limit.period_end
            )

        # Increment the usage
        rate_limit.current_usage += increment

        return {
            "resource": resource,
            "current_usage": rate_limit.current_usage,
            "max_usage": rate_limit.max_usage,
            "remaining": rate_limit.remaining_requests(),
            "reset_time": rate_limit.period_end,
            "period_type": period_type,
            "user_id": user_id,
        }


async def get_rate_limit_status(
    resource: str, period_type: str = "day", user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the current rate limit status for a resource.

    Args:
        resource: Name of the resource
        period_type: Type of period
        user_id: Optional user-specific rate limiting

    Returns:
        Rate limit information or None if no limit exists
    """
    async with get_rate_limit_session() as session:
        period_start, period_end = RateLimit.get_period_bounds(period_type)

        stmt = select(RateLimit).where(
            RateLimit.resource_name == resource,
            RateLimit.period_start == period_start,
            RateLimit.user_id == user_id,
        )

        result = await session.execute(stmt)
        rate_limit = result.scalar_one_or_none()

        if rate_limit is None:
            return None

        return {
            "resource": resource,
            "current_usage": rate_limit.current_usage,
            "max_usage": rate_limit.max_usage,
            "remaining": rate_limit.remaining_requests(),
            "reset_time": rate_limit.period_end,
            "period_type": period_type,
            "user_id": user_id,
            "is_exceeded": rate_limit.is_exceeded(),
        }


def rate_limited(
    resource: str,
    max_requests: int,
    period: str = "day",
    per_user: bool = False,
    cost: int = 1,
) -> Callable[[F], F]:
    """
    Decorator to add rate limiting to a function.

    Args:
        resource: Name of the resource to rate limit
        max_requests: Maximum requests allowed per period
        period: Period type ('minute', 'hour', 'day', 'month')
        per_user: Whether to apply rate limiting per user
        cost: Number of requests this call counts as (default 1)

    Returns:
        Decorated function that enforces rate limiting

    Example:
        @rate_limited(resource='google-search', max_requests=100, period='day')
        async def search_web(query: str) -> str:
            # This function can only be called 100 times per day total
            pass

        @rate_limited(resource='openai-api', max_requests=50, period='hour', per_user=True)
        async def generate_image(prompt: str) -> str:
            # Each user can call this 50 times per hour
            pass
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Determine user_id for per-user rate limiting
            user_id = None
            if per_user:
                # Try to get user_id from Discord context
                from ..tools.discord_context import get_discord_context

                try:
                    discord_context = get_discord_context()
                    if (
                        discord_context
                        and hasattr(discord_context, "user")
                        and discord_context.user
                    ):
                        user_id = str(discord_context.user.id)
                except Exception as e:
                    logger.warning(
                        f"Could not get Discord context for rate limiting: {e}"
                    )

            # Check and increment rate limit
            try:
                rate_info = await check_and_increment_rate_limit(
                    resource=resource,
                    max_requests=max_requests,
                    period_type=period,
                    user_id=user_id,
                    increment=cost,
                )

                logger.debug(
                    f"Rate limit OK for {resource}: {rate_info['current_usage']}/{rate_info['max_usage']} "
                    f"({rate_info['remaining']} remaining)"
                )

                # Call the original function
                return await func(*args, **kwargs)

            except RateLimitExceeded as e:
                logger.warning(f"Rate limit exceeded: {e}")

                # Return a user-friendly error message
                reset_delta = e.reset_time - datetime.now(UTC)
                reset_seconds = max(0, int(reset_delta.total_seconds()))

                if reset_seconds < 60:
                    reset_msg = f"{reset_seconds} seconds"
                elif reset_seconds < 3600:
                    reset_msg = f"{reset_seconds // 60} minutes"
                elif reset_seconds < 86400:
                    reset_msg = f"{reset_seconds // 3600} hours"
                else:
                    reset_msg = f"{reset_seconds // 86400} days"

                return (
                    f"⚠️ Rate limit reached for {resource}. "
                    f"You've used {e.limit} requests. "
                    f"Limit resets in {reset_msg}."
                )

        return cast(F, wrapper)

    return decorator


async def cleanup_expired_rate_limits() -> int:
    """
    Clean up expired rate limit records from the database.

    Returns:
        Number of records cleaned up
    """
    async with get_rate_limit_session() as session:
        now = datetime.now(UTC)

        # Delete expired rate limit records
        stmt = select(RateLimit).where(RateLimit.period_end < now)
        result = await session.execute(stmt)
        expired_limits = result.scalars().all()

        count = len(expired_limits)

        if count > 0:
            for limit in expired_limits:
                await session.delete(limit)

            await session.commit()
            logger.info(f"Cleaned up {count} expired rate limit records")

        return count
