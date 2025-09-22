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

from mobo.db import get_session_maker
from mobo.services import RateLimitService
from mobo.exceptions import RateLimitExceeded

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


async def check_and_increment_rate_limit(
    resource: str,
    max_requests: int,
    period_type: str = "day",
    increment: int = 1,
) -> Dict[str, Any]:
    """
    Check if a rate limit allows the request and increment usage.

    Args:
        resource: Name of the resource (e.g., 'google-search')
        max_requests: Maximum requests allowed in the period
        period_type: Type of period ('minute', 'hour', 'day', 'month')
        increment: Number of requests to increment by

    Returns:
        Dictionary with rate limit information

    Raises:
        RateLimitExceeded: If the rate limit would be exceeded
    """
    rate_limit_service = RateLimitService()
    async with get_rate_limit_session() as session:
        # Use service for business logic
        return await rate_limit_service.check_and_increment(
            session=session,
            resource=resource,
            max_requests=max_requests,
            period_type=period_type,
            increment=increment,
        )


async def get_rate_limit_status(
    resource: str, period_type: str = "day"
) -> Optional[Dict[str, Any]]:
    """
    Get the current rate limit status for a resource.

    Args:
        resource: Name of the resource
        period_type: Type of period

    Returns:
        Rate limit information or None if no limit exists
    """
    rate_limit_service = RateLimitService()
    async with get_rate_limit_session() as session:
        return await rate_limit_service.get_status(
            session=session,
            resource=resource,
            period_type=period_type,
        )


def rate_limited(
    resource: str,
    max_requests: int,
    period: str = "day",
    cost: int = 1,
) -> Callable[[F], F]:
    """
    Decorator to add rate limiting to a function.

    Args:
        resource: Name of the resource to rate limit
        max_requests: Maximum requests allowed per period
        period: Period type ('minute', 'hour', 'day', 'month')
        cost: Number of requests this call counts as (default 1)

    Returns:
        Decorated function that enforces rate limiting

    Example:
        @rate_limited(resource='google-search', max_requests=100, period='day')
        async def search_web(query: str) -> str:
            # This function can only be called 100 times per day total
            pass

        @rate_limited(resource='openai-api', max_requests=50, period='hour', cost=2)
        async def generate_image(prompt: str) -> str:
            # This function costs 2 requests and can be called up to 25 times per hour
            pass
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check and increment rate limit
            try:
                rate_info = await check_and_increment_rate_limit(
                    resource=resource,
                    max_requests=max_requests,
                    period_type=period,
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
                now = datetime.now(UTC)
                reset_delta = e.reset_time - now
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
    rate_limit_service = RateLimitService()
    async with get_rate_limit_session() as session:
        count = await rate_limit_service.cleanup_expired(session)
        if count > 0:
            logger.info(f"Cleaned up {count} expired rate limit records")
        return count
