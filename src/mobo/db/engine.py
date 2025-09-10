"""
Database engine management with proper lifecycle handling.
"""

import atexit
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from mobo.config import get_settings

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine with proper lifecycle management."""
    global _engine

    if _engine is None:
        settings = get_settings()
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
        import asyncio

        try:
            # Try to dispose cleanly
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, schedule disposal
                loop.create_task(_engine.dispose())
            else:
                # If no loop is running, run disposal synchronously
                asyncio.run(_engine.dispose())
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")
        finally:
            _engine = None


async def dispose_engine():
    """Manually dispose of the engine (useful for tests and graceful shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.debug("Database engine disposed")
