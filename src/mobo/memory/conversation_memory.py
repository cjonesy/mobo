"""LangChain conversation memory implementation."""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.memory import BaseMemory
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import Field

from .rag_memory import RAGMemory

logger = logging.getLogger(__name__)


class ConversationMemory(BaseMemory):
    """LangChain-compatible conversation memory with RAG backing."""

    rag_memory: RAGMemory = Field(default_factory=RAGMemory)
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    max_memory_length: int = 10
    memory_key: str = "chat_history"
    input_key: str = "input"
    output_key: str = "output"

    class Config:
        arbitrary_types_allowed = True

    @property
    def memory_variables(self) -> List[str]:
        """Return memory variables."""
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables from storage."""
        # For now, return empty as we handle context in the agent
        return {self.memory_key: []}

    async def aload_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Async load memory variables from storage."""
        if not self.channel_id:
            return {self.memory_key: []}

        try:
            # Get recent messages for conversational context
            recent_messages = await self.rag_memory.get_recent_messages(
                channel_id=self.channel_id, limit=self.max_memory_length
            )

            # Convert to LangChain message format
            messages: list[HumanMessage | AIMessage] = []
            for msg in recent_messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

            return {self.memory_key: messages}

        except Exception as e:
            logger.error(f"Error loading memory variables: {e}")
            return {self.memory_key: []}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """Save context (synchronous - not used in async context)."""
        pass

    async def asave_context(
        self, inputs: Dict[str, Any], outputs: Dict[str, Any]
    ) -> None:
        """Save context to storage."""
        if not self.user_id or not self.channel_id:
            logger.warning("Missing user_id or channel_id for saving context")
            return

        try:
            # Save user input
            user_input = inputs.get(self.input_key, "")
            if user_input:
                await self.rag_memory.store_message(
                    user_id=self.user_id,
                    channel_id=self.channel_id,
                    role="user",
                    content=user_input,
                )

            # Save assistant output
            assistant_output = outputs.get(self.output_key, "")
            if assistant_output:
                await self.rag_memory.store_message(
                    user_id=self.user_id,
                    channel_id=self.channel_id,
                    role="assistant",
                    content=assistant_output,
                )

        except Exception as e:
            logger.error(f"Error saving context: {e}")

    def clear(self) -> None:
        """Clear memory (not implemented for persistent storage)."""
        pass

    def set_context(self, user_id: str, channel_id: str) -> None:
        """Set the context for this memory instance."""
        self.user_id = user_id
        self.channel_id = channel_id
