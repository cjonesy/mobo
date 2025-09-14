"""
Base repository class for async database operations.

This module provides the base AsyncRepository class that all other
repositories inherit from, providing common CRUD operations.
"""

from typing import Generic, TypeVar, Type, Optional, Sequence, Callable
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class AsyncRepository(Generic[T]):
    """Base async repository with common CRUD operations."""

    def __init__(self, model: Type[T]):
        self.model = model

    async def get(self, session: AsyncSession, obj_id: int) -> Optional[T]:
        """Get a single object by ID."""
        return await session.get(self.model, obj_id)

    async def add(self, session: AsyncSession, obj: T) -> T:
        """Add an object to the session."""
        session.add(obj)
        return obj

    async def list(
        self,
        session: AsyncSession,
        where: Optional[Callable[[Select], Select]] = None,
        limit: int = 50,
        offset: int = 0,
        order_by=None,
    ) -> Sequence[T]:
        """List objects with optional filtering, ordering, and pagination."""
        stmt: Select = select(self.model)
        if where:
            stmt = where(stmt)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def delete(self, session: AsyncSession, obj: T) -> None:
        """Delete an object from the session."""
        await session.delete(obj)
