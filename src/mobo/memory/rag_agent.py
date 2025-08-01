"""Intelligent RAG agent for memory retrieval and query analysis."""

import logging
import textwrap
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .rag_memory import RAGMemory
from ..config import get_config

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of queries the RAG agent can handle."""

    TEMPORAL = "temporal"  # Questions about timing, order, first/last things
    SEMANTIC = "semantic"  # Questions about specific topics or content
    PERSONAL = "personal"  # Questions about user information, names, preferences
    RECENT = "recent"  # Questions about recent conversations
    GENERAL = "general"  # General questions that need broad context


class RetrievalStrategy(BaseModel):
    """Strategy for retrieving relevant messages."""

    query_type: QueryType = Field(description="The type of query being made")
    similarity_threshold: float = Field(
        description="Similarity threshold for vector search (0.3-0.8)"
    )
    prioritize_chronological: bool = Field(
        description="Whether to prioritize chronological order"
    )
    include_earliest: bool = Field(description="Whether to include earliest messages")
    include_recent: bool = Field(description="Whether to include recent messages")
    max_messages: int = Field(description="Maximum number of messages to retrieve")
    reasoning: str = Field(description="Brief explanation of the strategy chosen")


@dataclass
class RAGResult:
    """Result from RAG retrieval with context and metadata."""

    context: str
    strategy_used: RetrievalStrategy
    message_count: int
    sources: List[Dict[str, Any]]


class RAGAgent:
    """Intelligent agent for analyzing queries and retrieving relevant context."""

    def __init__(self) -> None:
        self.config = get_config()
        self.rag_memory = RAGMemory()

        # Use a cheaper, faster model for RAG analysis
        self.llm = ChatOpenAI(
            model=self.config.rag_model,  # Configurable model with gpt-4o-mini default
            temperature=0.1,  # Low temperature for more consistent analysis
            api_key=self.config.openai_api_key,
        )

        self.parser = PydanticOutputParser(pydantic_object=RetrievalStrategy)
        self.prompt = self._create_analysis_prompt()

    def _create_analysis_prompt(self) -> ChatPromptTemplate:
        """Create the prompt for analyzing user queries."""
        system_prompt = textwrap.dedent(
            """
            You are a specialized RAG (Retrieval-Augmented Generation) agent that analyzes user queries to determine the best strategy for retrieving relevant conversation history.

            Your job is to understand what the user is asking and decide:
            1. What type of query this is (temporal, semantic, personal, etc.)
            2. What similarity threshold to use for vector search
            3. Whether to prioritize chronological order or semantic similarity
            4. Whether to include earliest/recent messages
            5. How many messages to retrieve

            Guidelines:
            - TEMPORAL queries (first/last/beginning/initial/early/recent): Lower similarity threshold (0.4-0.5), prioritize chronological order
            - SEMANTIC queries (about specific topics): Higher similarity threshold (0.6-0.7), prioritize semantic similarity
            - PERSONAL queries (names, preferences, user info): Medium similarity threshold (0.5-0.6), include both early and recent messages
            - RECENT queries (what just happened): High similarity threshold (0.6-0.8), focus on recent messages only
            - GENERAL queries: Medium settings, balanced approach

            Consider context carefully - a question like "What did we first talk about?" is temporal, while "What did we talk about regarding cats?" is semantic.

            {format_instructions}
        """
        ).strip()

        return ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                (
                    "human",
                    "Analyze this user query and determine the best retrieval strategy: {query}",
                ),
            ]
        )

    async def analyze_and_retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> RAGResult:
        """Analyze the query and retrieve relevant context using the determined strategy."""
        try:
            # Step 1: Analyze the query to determine strategy
            strategy = await self._analyze_query(query)
            logger.debug(
                f"RAG strategy for '{query[:50]}...': {strategy.query_type}, threshold={strategy.similarity_threshold}"
            )

            # Step 2: Retrieve messages based on the strategy
            messages = await self._retrieve_with_strategy(
                strategy, query, user_id, channel_id
            )

            # Step 3: Format the context
            context = self._format_context(messages, strategy)

            return RAGResult(
                context=context,
                strategy_used=strategy,
                message_count=len(messages),
                sources=messages,
            )

        except Exception as e:
            logger.error(f"Error in RAG analysis and retrieval: {e}")
            # Fallback to simple semantic search
            fallback_messages = await self.rag_memory.get_similar_messages(
                query=query,
                user_id=user_id,
                channel_id=channel_id,
                limit=5,
                similarity_threshold=0.5,
            )
            return RAGResult(
                context=self._format_context(fallback_messages, None),
                strategy_used=RetrievalStrategy(
                    query_type=QueryType.GENERAL,
                    similarity_threshold=0.5,
                    prioritize_chronological=False,
                    include_earliest=False,
                    include_recent=True,
                    max_messages=5,
                    reasoning="Fallback strategy due to analysis error",
                ),
                message_count=len(fallback_messages),
                sources=fallback_messages,
            )

    async def _analyze_query(self, query: str) -> RetrievalStrategy:
        """Use LLM to analyze the query and determine retrieval strategy."""
        try:
            formatted_prompt = self.prompt.format_prompt(
                query=query, format_instructions=self.parser.get_format_instructions()
            )

            response = await self.llm.ainvoke(formatted_prompt.to_messages())
            # Ensure content is a string for parsing
            content = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )
            strategy = self.parser.parse(content)

            # Validate and adjust strategy if needed
            strategy.similarity_threshold = max(
                0.3, min(0.8, strategy.similarity_threshold)
            )
            strategy.max_messages = max(1, min(20, strategy.max_messages))

            return strategy

        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            # Return a safe default strategy
            return RetrievalStrategy(
                query_type=QueryType.GENERAL,
                similarity_threshold=0.5,
                prioritize_chronological=False,
                include_earliest=False,
                include_recent=True,
                max_messages=5,
                reasoning="Default strategy due to analysis error",
            )

    async def _retrieve_with_strategy(
        self,
        strategy: RetrievalStrategy,
        query: str,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve messages based on the determined strategy."""
        all_messages = []
        seen_ids = set()

        # For conversation context, we typically want the full channel history
        # Only use user_id filtering for personal queries
        filter_user_id = user_id if strategy.query_type == QueryType.PERSONAL else None

        # Get different types of messages based on strategy
        if strategy.include_earliest:
            earliest_messages = await self.rag_memory.get_earliest_messages(
                user_id=filter_user_id,
                channel_id=channel_id,
                limit=min(10, strategy.max_messages),
            )
            for msg in earliest_messages:
                if msg["id"] not in seen_ids:
                    seen_ids.add(msg["id"])
                    all_messages.append(msg)

        # Always get semantically similar messages (with custom threshold)
        similar_messages = await self.rag_memory.get_similar_messages(
            query=query,
            user_id=filter_user_id,
            channel_id=channel_id,
            limit=strategy.max_messages,
            similarity_threshold=strategy.similarity_threshold,
        )
        for msg in similar_messages:
            if msg["id"] not in seen_ids:
                seen_ids.add(msg["id"])
                all_messages.append(msg)

        if strategy.include_recent:
            recent_messages = await self.rag_memory.get_recent_messages(
                user_id=filter_user_id,
                channel_id=channel_id,
                limit=min(10, strategy.max_messages),
            )
            for msg in recent_messages:
                if msg["id"] not in seen_ids:
                    seen_ids.add(msg["id"])
                    all_messages.append(msg)

        # Sort and limit based on strategy
        if strategy.prioritize_chronological:
            all_messages.sort(key=lambda x: x["timestamp"])
        else:
            # For semantic queries, we want the most relevant messages
            # The similar_messages are already sorted by relevance
            pass

        return all_messages[: strategy.max_messages]

    def _format_context(
        self, messages: List[Dict[str, Any]], strategy: Optional[RetrievalStrategy]
    ) -> str:
        """Format retrieved messages into context string."""
        if not messages:
            return ""

        context = "Recent conversation context:\n"
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context += f"- {role}: {content}\n"

        return context

    async def close(self) -> None:
        """Close resources."""
        await self.rag_memory.close()
