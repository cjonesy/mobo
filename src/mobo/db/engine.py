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
        try:
            # At exit time, the event loop is usually closed or closing
            # Just dispose synchronously without trying to use the loop
            logger.debug("Disposing database engine synchronously")
            import asyncio
            
            # Check if we have a running loop first
            try:
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    # Schedule disposal in the existing loop
                    loop.create_task(_engine.dispose())
                    return
            except RuntimeError:
                # No event loop running
                pass
            
            # Fallback: Create a new event loop for cleanup
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(_engine.dispose())
            finally:
                new_loop.close()
                
        except Exception as e:
            # Engine disposal failed, but don't crash the exit process
            logger.debug(f"Engine disposal failed during cleanup: {e}")
        finally:
            _engine = None
