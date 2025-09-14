"""
Rate limit repository for database operations.

This repository handles all database operations related to rate limiting,
providing a clean interface for rate limit checking and management.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .base import AsyncRepository
from ..models.rate_limit import RateLimit


class RateLimitRepository(AsyncRepository[RateLimit]):
    """Repository for RateLimit model operations."""

    def __init__(self):
        super().__init__(RateLimit)

    async def get_rate_limit(
        self,
        session: AsyncSession,
        resource_name: str,
        period_start: datetime,
        user_id: Optional[str] = None,
    ) -> Optional[RateLimit]:
        """Get a rate limit record for a specific resource and period."""
        stmt = select(RateLimit).where(
            RateLimit.resource_name == resource_name,
            RateLimit.period_start == period_start,
            RateLimit.user_id == user_id,
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_rate_limit(
        self,
        session: AsyncSession,
        resource_name: str,
        period_start: datetime,
        period_end: datetime,
        max_usage: int,
        period_type: str,
        user_id: Optional[str] = None,
        current_usage: int = 0,
    ) -> RateLimit:
        """Create a new rate limit record."""
        rate_limit = RateLimit(
            resource_name=resource_name,
            period_start=period_start,
            period_end=period_end,
            current_usage=current_usage,
            max_usage=max_usage,
            user_id=user_id,
            period_type=period_type,
        )

        session.add(rate_limit)
        await session.flush()
        return rate_limit

    async def get_or_create_rate_limit(
        self,
        session: AsyncSession,
        resource_name: str,
        period_start: datetime,
        period_end: datetime,
        max_usage: int,
        period_type: str,
        user_id: Optional[str] = None,
    ) -> RateLimit:
        """Get existing rate limit or create a new one for the given period."""
        # Try to get existing rate limit
        rate_limit = await self.get_rate_limit(
            session, resource_name, period_start, user_id
        )

        if rate_limit is None:
            # Create new rate limit
            rate_limit = await self.create_rate_limit(
                session=session,
                resource_name=resource_name,
                period_start=period_start,
                period_end=period_end,
                max_usage=max_usage,
                period_type=period_type,
                user_id=user_id,
                current_usage=0,
            )

        return rate_limit

    async def update_usage(
        self,
        session: AsyncSession,
        rate_limit: RateLimit,
        increment: int = 1,
    ) -> RateLimit:
        """Update the usage count for a rate limit."""
        rate_limit.current_usage = rate_limit.current_usage + increment
        await session.flush()
        return rate_limit

    async def get_rate_limit_status(
        self,
        session: AsyncSession,
        resource_name: str,
        period_start: datetime,
        period_type: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the current status of a rate limit for the given period."""
        rate_limit = await self.get_rate_limit(
            session, resource_name, period_start, user_id
        )

        if rate_limit is None:
            return None

        return {
            "resource": resource_name,
            "current_usage": rate_limit.current_usage,
            "max_usage": rate_limit.max_usage,
            "reset_time": rate_limit.period_end,
            "period_type": period_type,
            "user_id": user_id,
        }

    async def delete_expired_before(
        self, session: AsyncSession, before_time: datetime
    ) -> int:
        """
        Delete rate limit records that expired before the given time.

        Args:
            session: Database session
            before_time: Delete records that expired before this time

        Returns:
            Number of records deleted
        """
        stmt = delete(RateLimit).where(RateLimit.period_end < before_time)
        result = await session.execute(stmt)
        return result.rowcount or 0
