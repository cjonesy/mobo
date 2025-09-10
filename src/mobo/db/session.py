"""
Database session management with lazy initialization.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from .engine import get_engine

# Global session maker instance
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session maker."""
    global _session_maker

    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _session_maker
