"""RAG memory system with embeddings and vector similarity search."""

import logging
import textwrap
from typing import Optional, Any, Sequence

from sqlalchemy import text, Result
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.engine import Row
from langchain_openai import OpenAIEmbeddings

from ..config import Config, get_config

logger = logging.getLogger(__name__)


class RAGMemory:
    """RAG memory system for storing and retrieving conversation context."""

    def __init__(self) -> None:
        self.config: Config = get_config()
        self.embeddings: OpenAIEmbeddings = OpenAIEmbeddings(
            api_key=self.config.openai_api_key,
            model=self.config.embedding_model,
        )
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
        """Initialize database tables if they don't exist."""
        async with self.engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Create conversation_memory table
            create_table_sql = textwrap.dedent(
                """
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    channel_id TEXT,
                    role TEXT, -- 'user' or 'assistant'
                    content TEXT,
                    embedding VECTOR(1536),
                    timestamp TIMESTAMP DEFAULT now()
                )
            """
            ).strip()
            await conn.execute(text(create_table_sql))

            # Create vector similarity index
            create_index_sql = textwrap.dedent(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_embedding
                ON conversation_memory
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """
            ).strip()
            await conn.execute(text(create_index_sql))

    async def store_message(
        self, user_id: str, channel_id: str, role: str, content: str
    ) -> None:
        """Store a message with its embedding in the conversation memory."""
        try:
            # Generate embedding for the content
            embedding_vector: list[float] = await self.embeddings.aembed_query(content)

            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(map(str, embedding_vector)) + "]"

            async with self.async_session() as session:
                await session.execute(
                    text(
                        f"""
                        INSERT INTO conversation_memory (user_id, channel_id, role, content, embedding)
                        VALUES (:user_id, :channel_id, :role, :content, '{embedding_str}'::vector)
                    """
                    ),
                    {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "role": role,
                        "content": content,
                    },
                )
                await session.commit()

            logger.debug(f"Stored message from {user_id} in channel {channel_id}")

        except Exception as e:
            logger.error(f"Failed to store message: {e}")

    async def get_similar_messages(
        self,
        query: str,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        limit: int = 5,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Retrieve similar messages using vector similarity search."""
        try:
            # Generate embedding for the query
            query_embedding: list[float] = await self.embeddings.aembed_query(query)

            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

            # Build the SQL query with optional filters
            where_clauses: list[str] = []
            params: dict[str, Any] = {
                "limit": limit,
            }

            if channel_id:
                where_clauses.append("channel_id = :channel_id")
                params["channel_id"] = channel_id

            if user_id:
                where_clauses.append("user_id = :user_id")
                params["user_id"] = user_id

            where_clause: str = (
                f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            )

            sql_query = textwrap.dedent(
                f"""
                WITH similarity_scores AS (
                    SELECT id, user_id, channel_id, role, content, timestamp,
                           1 - (embedding <=> '{embedding_str}'::vector) AS similarity
                    FROM conversation_memory
                    {where_clause}
                )
                SELECT *
                FROM similarity_scores
                WHERE similarity > {similarity_threshold}
                ORDER BY similarity DESC
                LIMIT :limit
            """
            ).strip()

            async with self.async_session() as session:
                result: Result[Any] = await session.execute(text(sql_query), params)
                rows: Sequence[Row[Any]] = result.fetchall()

                return [
                    {
                        "id": row.id,
                        "user_id": row.user_id,
                        "channel_id": row.channel_id,
                        "role": row.role,
                        "content": row.content,
                        "timestamp": row.timestamp,
                        "similarity": float(row.similarity),
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to retrieve similar messages: {e}")
            return []

    async def get_recent_messages(
        self,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve recent messages for context."""
        try:
            where_clauses: list[str] = []
            params: dict[str, Any] = {"limit": limit}

            if user_id:
                where_clauses.append("user_id = :user_id")
                params["user_id"] = user_id

            if channel_id:
                where_clauses.append("channel_id = :channel_id")
                params["channel_id"] = channel_id

            where_clause: str = (
                f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            )

            sql_query = textwrap.dedent(
                f"""
                SELECT id, user_id, channel_id, role, content, timestamp
                FROM conversation_memory
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT :limit
            """
            ).strip()

            async with self.async_session() as session:
                result: Result[Any] = await session.execute(text(sql_query), params)
                rows: Sequence[Row[Any]] = result.fetchall()

                return [
                    {
                        "id": row.id,
                        "user_id": row.user_id,
                        "channel_id": row.channel_id,
                        "role": row.role,
                        "content": row.content,
                        "timestamp": row.timestamp,
                    }
                    for row in reversed(rows)  # Return in chronological order
                ]

        except Exception as e:
            logger.error(f"Failed to retrieve recent messages: {e}")
            return []

    async def get_earliest_messages(
        self,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve the earliest messages chronologically for context."""
        try:
            where_clauses: list[str] = []
            params: dict[str, Any] = {"limit": limit}

            if user_id:
                where_clauses.append("user_id = :user_id")
                params["user_id"] = user_id

            if channel_id:
                where_clauses.append("channel_id = :channel_id")
                params["channel_id"] = channel_id

            where_clause: str = (
                f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            )

            sql_query = textwrap.dedent(
                f"""
                SELECT id, user_id, channel_id, role, content, timestamp
                FROM conversation_memory
                {where_clause}
                ORDER BY timestamp ASC
                LIMIT :limit
            """
            ).strip()

            async with self.async_session() as session:
                result: Result[Any] = await session.execute(text(sql_query), params)
                rows: Sequence[Row[Any]] = result.fetchall()

                return [
                    {
                        "id": row.id,
                        "user_id": row.user_id,
                        "channel_id": row.channel_id,
                        "role": row.role,
                        "content": row.content,
                        "timestamp": row.timestamp,
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to retrieve earliest messages: {e}")
            return []

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()
