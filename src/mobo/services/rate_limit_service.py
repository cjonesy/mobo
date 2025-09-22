"""
Rate limiting service for business logic and coordination.

This service provides high-level rate limiting operations,
coordinating between repositories and handling business rules.
"""

from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.rate_limit_repository import RateLimitRepository
from ..models.rate_limit import RateLimit
from ..exceptions import RateLimitExceeded

logger = logging.getLogger(__name__)


class RateLimitService:
    """Service for rate limiting business operations."""

    def __init__(self):
        self.repository = RateLimitRepository()

    async def check_and_increment(
        self,
        session: AsyncSession,
        resource: str,
        max_requests: int,
        period_type: str = "day",
        increment: int = 1,
    ) -> Dict[str, Any]:
        """
        Check if a rate limit allows the request and increment usage.

        Args:
            session: Database session
            resource: Name of the resource (e.g., 'google-search')
            max_requests: Maximum requests allowed in the period
            period_type: Type of period ('minute', 'hour', 'day', 'month')
            increment: Number of requests to increment by

        Returns:
            Dictionary with rate limit information

        Raises:
            RateLimitExceeded: If the rate limit would be exceeded
        """
        # Calculate period bounds (business logic)
        period_start, period_end = self.get_period_bounds(period_type)

        # Get or create rate limit record (data access)
        rate_limit = await self.repository.get_or_create_rate_limit(
            session=session,
            resource_name=resource,
            period_start=period_start,
            period_end=period_end,
            max_usage=max_requests,
            period_type=period_type,
            user_id=None,
        )

        # Business logic: check if request is allowed
        if self.is_exceeded(rate_limit, increment):
            raise RateLimitExceeded(
                resource, rate_limit.max_usage, rate_limit.period_end
            )

        # Update usage (data access)
        rate_limit = await self.repository.update_usage(session, rate_limit, increment)

        return {
            "resource": resource,
            "current_usage": rate_limit.current_usage,
            "max_usage": rate_limit.max_usage,
            "remaining": self.remaining_requests(rate_limit),
            "reset_time": rate_limit.period_end,
            "period_type": period_type,
        }

    async def get_status(
        self,
        session: AsyncSession,
        resource: str,
        period_type: str = "day",
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a rate limit.

        Args:
            session: Database session
            resource: Name of the resource
            period_type: Type of period ('minute', 'hour', 'day', 'month')

        Returns:
            Dictionary with rate limit status or None if no limit exists
        """
        # Calculate period bounds (business logic)
        period_start, _ = self.get_period_bounds(period_type)

        status = await self.repository.get_rate_limit_status(
            session=session,
            resource_name=resource,
            period_start=period_start,
            period_type=period_type,
            user_id=None,
        )

        if status is None:
            return None

        # Add business logic fields
        rate_limit = await self.repository.get_rate_limit(
            session, resource, period_start, None
        )

        if rate_limit:
            status["remaining"] = self.remaining_requests(rate_limit)
            status["is_exceeded"] = self.is_exceeded(rate_limit)

        return status

    async def cleanup_expired(
        self,
        session: AsyncSession,
        before_time: Optional[datetime] = None,
    ) -> int:
        """
        Clean up expired rate limits.

        Args:
            session: Database session
            before_time: Clean up limits before this time (defaults to now)

        Returns:
            Number of expired limits cleaned up
        """
        if before_time is None:
            before_time = datetime.now(UTC)

        return await self.repository.delete_expired_before(
            session=session,
            before_time=before_time,
        )

    def is_exceeded(self, rate_limit: RateLimit, increment: int = 1) -> bool:
        """Check if the rate limit has been or would be exceeded."""
        return bool(rate_limit.current_usage + increment > rate_limit.max_usage)

    def can_make_requests(self, rate_limit: RateLimit, count: int = 1) -> bool:
        """Check if we can make the specified number of requests."""
        return bool((rate_limit.current_usage + count) <= rate_limit.max_usage)

    def remaining_requests(self, rate_limit: RateLimit) -> int:
        """Get the number of remaining requests in this period."""
        return max(0, int(rate_limit.max_usage) - int(rate_limit.current_usage))

    def time_until_reset(self, rate_limit: RateLimit) -> timedelta:
        """Get time until this rate limit period resets."""
        # Use consistent UTC timezone-aware datetimes
        now = datetime.now(UTC)
        period_end = (
            rate_limit.period_end
            if isinstance(rate_limit.period_end, datetime)
            else datetime.fromisoformat(str(rate_limit.period_end))
        )
        # Ensure period_end is timezone-aware UTC
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=UTC)

        if now >= period_end:
            return timedelta(0)
        return period_end - now

    def get_period_bounds(
        self, period_type: str, base_time: datetime | None = None
    ) -> tuple[datetime, datetime]:
        """
        Get the start and end times for a rate limit period.

        Args:
            period_type: Type of period ('minute', 'hour', 'day', 'month')
            base_time: Base time to calculate from (defaults to now)

        Returns:
            Tuple of (period_start, period_end)
        """
        if base_time is None:
            base_time = datetime.now(UTC)

        if period_type == "minute":
            start = base_time.replace(second=0, microsecond=0)
            end = start + timedelta(minutes=1)
        elif period_type == "hour":
            start = base_time.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period_type == "day":
            start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period_type == "month":
            # First day of current month
            start = base_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # First day of next month
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:
            raise ValueError(f"Invalid period type: {period_type}")

        # Return timezone-aware UTC datetimes for consistency
        return start, end
