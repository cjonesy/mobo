"""Bot interaction tracking for anti-loop protection."""

import logging
from typing import Tuple, Optional, Any
from datetime import datetime, timedelta

from sqlalchemy import text, Result
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.engine import Row

from ..config import Config, get_config

logger = logging.getLogger(__name__)


class BotInteractionTracker:
    """Tracks bot interactions to prevent infinite loops between bots."""

    def __init__(self) -> None:
        self.config: Config = get_config()
        self.engine: AsyncEngine = create_async_engine(
            self.config.database_url,
            echo=self.config.database_echo,
            pool_size=self.config.database_pool_size,
            max_overflow=self.config.database_max_overflow,
        )
        self.async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize_database(self) -> None:
        """Initialize bot interactions table if it doesn't exist."""
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS bot_interactions (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    interaction_count INTEGER DEFAULT 0,
                    last_interaction TIMESTAMP DEFAULT now(),
                    is_bot BOOLEAN DEFAULT false,
                    UNIQUE(user_id, channel_id)
                )
            """
                )
            )

            await conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_bot_interactions_user_channel
                ON bot_interactions (user_id, channel_id)
            """
                )
            )

    async def update_bot_interaction(
        self, user_id: str, channel_id: str, is_bot: bool
    ) -> None:
        """Update bot interaction count for a user in a channel."""
        try:
            async with self.async_session() as session:
                if is_bot:
                    # Increment bot interaction count
                    await session.execute(
                        text(
                            """
                            INSERT INTO bot_interactions (user_id, channel_id, interaction_count, is_bot, last_interaction)
                            VALUES (:user_id, :channel_id, 1, true, now())
                            ON CONFLICT (user_id, channel_id)
                            DO UPDATE SET
                                interaction_count = bot_interactions.interaction_count + 1,
                                last_interaction = now(),
                                is_bot = true
                        """
                        ),
                        {"user_id": user_id, "channel_id": channel_id},
                    )
                else:
                    # Reset bot interaction count for human users in this channel
                    await session.execute(
                        text(
                            """
                            UPDATE bot_interactions
                            SET interaction_count = 0, last_interaction = now(), is_bot = false
                            WHERE channel_id = :channel_id
                        """
                        ),
                        {"channel_id": channel_id},
                    )

                await session.commit()

        except Exception as e:
            logger.error(f"Failed to update bot interaction for {user_id}: {e}")

    async def can_respond_to_bot(
        self, user_id: str, channel_id: str
    ) -> Tuple[bool, str]:
        """Check if bot can respond to another bot based on interaction limits."""
        try:
            async with self.async_session() as session:
                result: Result[Tuple[int, bool, datetime]] = await session.execute(
                    text(
                        """
                        SELECT interaction_count, is_bot, last_interaction
                        FROM bot_interactions
                        WHERE user_id = :user_id AND channel_id = :channel_id
                    """
                    ),
                    {"user_id": user_id, "channel_id": channel_id},
                )
                row: Optional[Row[Tuple[int, bool, datetime]]] = result.fetchone()

                if not row:
                    return True, "No previous interactions recorded"

                if not row.is_bot:
                    return True, "User is not a bot"

                if row.interaction_count >= self.config.max_bot_responses:
                    return (
                        False,
                        f"Bot interaction limit reached ({row.interaction_count}/{self.config.max_bot_responses})",
                    )

                return (
                    True,
                    f"Bot interactions: {row.interaction_count}/{self.config.max_bot_responses}",
                )

        except Exception as e:
            logger.error(f"Failed to check bot interaction limits for {user_id}: {e}")
            return True, "Error checking limits, allowing response"

    async def reset_bot_interactions(self, channel_id: str) -> None:
        """Reset all bot interaction counts in a channel (when human joins)."""
        try:
            async with self.async_session() as session:
                await session.execute(
                    text(
                        """
                        UPDATE bot_interactions
                        SET interaction_count = 0, last_interaction = now()
                        WHERE channel_id = :channel_id
                    """
                    ),
                    {"channel_id": channel_id},
                )
                await session.commit()
                logger.debug(f"Reset bot interactions for channel {channel_id}")

        except Exception as e:
            logger.error(
                f"Failed to reset bot interactions for channel {channel_id}: {e}"
            )

    async def cleanup_old_interactions(self, days_old: int = 7) -> None:
        """Clean up old bot interaction records."""
        try:
            cutoff_date: datetime = datetime.now() - timedelta(days=days_old)
            async with self.async_session() as session:
                result: Any = await session.execute(
                    text(
                        """
                        DELETE FROM bot_interactions
                        WHERE last_interaction < :cutoff_date
                    """
                    ),
                    {"cutoff_date": cutoff_date},
                )
                await session.commit()
                logger.info(f"Cleaned up {result.rowcount} old bot interaction records")

        except Exception as e:
            logger.error(f"Failed to cleanup old interactions: {e}")

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
