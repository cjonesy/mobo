"""
Database engine management with proper lifecycle handling.
"""

import atexit
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from mobo.config import settings

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine with proper lifecycle management."""
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            url=settings.database.url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
        )

        # Register cleanup on application exit
        atexit.register(_cleanup_engine)
        logger.debug("Created async database engine")

    return _engine


def _cleanup_engine():
    """Clean up the engine on application exit."""
    global _engine
    if _engine is not None:
        # At exit time, async cleanup is problematic with asyncpg/greenlets
        # The OS will clean up connections anyway, so just clear the reference
        logger.debug("Clearing database engine reference at exit")
        _engine = None
