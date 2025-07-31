"""LangGraph agent with StateGraph implementation."""

import logging
from typing import Literal, Optional, Tuple, Any
from typing_extensions import TypedDict

import discord
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from pydantic import SecretStr

from .tools import get_all_tools, set_discord_context
from .memory import RAGMemory
from .user_profiles import UserProfileManager
from .bot_interaction_tracker import BotInteractionTracker
from ..config import get_config
from .types import BotResponse

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State schema for the LangGraph agent."""

    messages: list[BaseMessage]
    user_id: str
    channel_id: str
    user_profile: dict[str, Any]
    context_messages: list[dict[str, Any]]
    discord_client: Optional[discord.Member]
    guild_id: Optional[str]


class DiscordLangGraphAgent:
    """Discord bot agent using LangGraph for workflow orchestration."""

    def __init__(self) -> None:
        self.config = get_config()
        self.rag_memory = RAGMemory()
        self.user_profile_manager = UserProfileManager()
        self.bot_interaction_tracker = BotInteractionTracker()

        # Convert string to SecretStr for ChatOpenAI api_key parameter
        api_key_str = self.config.openai_api_key.get_secret_value()
        api_key_secret = SecretStr(api_key_str)

        self.llm = ChatOpenAI(
            model=self.config.openai_model,
            temperature=self.config.openai_temperature,
            api_key=api_key_secret,
        )

        self.tools = get_all_tools()
        self.tool_node = ToolNode(self.tools)

        self.llm_with_tools = self.llm.bind_tools(self.tools)

        self.graph = self._build_graph()

    def _filter_conversation_messages(
        self, messages: list[BaseMessage]
    ) -> list[BaseMessage]:
        """Filter out SystemMessages to get only conversation messages."""
        return [msg for msg in messages if not isinstance(msg, SystemMessage)]

    def _find_recent_messages_by_type(
        self, messages: list[BaseMessage]
    ) -> Tuple[Optional[HumanMessage], Optional[AIMessage]]:
        """Find the most recent HumanMessage and AIMessage from a list of messages."""
        user_message = None
        bot_response = None

        # Look for the most recent HumanMessage and AIMessage
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and bot_response is None:
                bot_response = msg
            elif isinstance(msg, HumanMessage) and user_message is None:
                user_message = msg

        return user_message, bot_response

    def _build_graph(self):
        """Build the LangGraph StateGraph for the agent workflow."""
        workflow = StateGraph(AgentState)

        workflow.add_node("get_context", self._get_context_node)
        workflow.add_node("llm", self._llm_node)
        workflow.add_node("tools", self.tool_node)
        workflow.add_node("update_user_profile", self._update_user_profile_node)

        workflow.set_entry_point("get_context")

        workflow.add_edge("get_context", "llm")
        workflow.add_conditional_edges(
            "llm",
            self._should_continue,
            {"continue": "tools", "end": "update_user_profile"},
        )
        workflow.add_edge("tools", "update_user_profile")
        workflow.add_edge("update_user_profile", END)

        return workflow.compile()

    async def _get_context_node(self, state: AgentState) -> dict[str, Any]:
        """Node to get RAG context and user profile."""
        try:
            user_id = state["user_id"]
            channel_id = state["channel_id"]

            # Get the latest user message
            latest_message = state["messages"][-1] if state["messages"] else None
            if not latest_message or not hasattr(latest_message, "content"):
                return {"context_messages": [], "user_profile": {}}

            user_profile = await self.user_profile_manager.get_user_profile(user_id)

            # Get similar messages for context using RAG
            similar_messages = await self.rag_memory.get_similar_messages(
                query=latest_message.text(),
                channel_id=channel_id,
                limit=self.config.top_k_memory_results,
            )

            # Get recent messages for continuity
            recent_messages = await self.rag_memory.get_recent_messages(
                channel_id=channel_id, limit=10
            )

            logger.debug(
                f"Retrieved {len(similar_messages)} similar messages and {len(recent_messages)} recent messages"
            )

            return {
                "user_profile": user_profile,
                "context_messages": similar_messages + recent_messages,
            }

        except Exception as e:
            logger.error(f"Error in get_context_node: {e}")
            return {"context_messages": [], "user_profile": {}}

    async def _llm_node(self, state: AgentState) -> dict[str, Any]:
        """Node to call the LLM with personality and context."""
        try:
            personality_prompt = await self.config.get_resolved_personality_prompt()

            user_profile = state.get("user_profile", {})
            if user_profile:
                tone = user_profile.get("tone", "neutral")
                likes = user_profile.get("likes", [])
                dislikes = user_profile.get("dislikes", [])

                parts = [f"Tone: {tone}"]
                if likes:
                    parts.append(f"Likes: {', '.join(likes[:3])}")
                if dislikes:
                    parts.append(f"Dislikes: {', '.join(dislikes[:3])}")

                profile_context = f"\nUser Profile - {', '.join(parts)}"
            else:
                profile_context = ""

            context_messages = state.get("context_messages", [])
            rag_context = ""
            if context_messages:
                rag_context = "\nRecent conversation context:\n"
                for msg in context_messages[
                    -self.config.max_context_messages :
                ]:  # Use only the most recent/relevant
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:200]  # Truncate long messages
                    rag_context += f"- {role}: {content}\n"

            system_message = f"{personality_prompt}{profile_context}{rag_context}"

            # Prepare messages for LLM - filter out any existing SystemMessages and ensure only one at the start
            conversation_messages = self._filter_conversation_messages(
                state["messages"]
            )
            messages = [SystemMessage(content=system_message)] + conversation_messages

            response = await self.llm_with_tools.ainvoke(messages)

            return {"messages": state["messages"] + [response]}

        except Exception as e:
            logger.error(f"Error in llm_node: {e}")
            error_response = AIMessage(
                content="I encountered an error processing your message."
            )
            return {"messages": state["messages"] + [error_response]}

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """Conditional edge function to determine if we should continue to tools."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None

        if (
            last_message
            and hasattr(last_message, "tool_calls")
            and last_message.tool_calls
        ):
            return "continue"
        return "end"

    async def _update_user_profile_node(self, state: AgentState) -> dict[str, Any]:
        """Node to store conversation in RAG memory after processing."""
        try:
            user_id = state["user_id"]
            channel_id = state["channel_id"]
            messages = state["messages"]

            # Filter out SystemMessages and find the actual conversation messages
            conversation_messages = self._filter_conversation_messages(messages)

            if len(conversation_messages) >= 2:
                # Find the most recent user and assistant messages by type, not position
                user_message, bot_response = self._find_recent_messages_by_type(
                    conversation_messages
                )

                if user_message and hasattr(user_message, "content"):
                    await self.rag_memory.store_message(
                        user_id=user_id,
                        channel_id=channel_id,
                        role="user",
                        content=user_message.text(),
                    )

                if bot_response and hasattr(bot_response, "content"):
                    await self.rag_memory.store_message(
                        user_id=user_id,
                        channel_id=channel_id,
                        role="assistant",
                        content=bot_response.text(),
                    )

            return {}

        except Exception as e:
            logger.error(f"Error in update_user_profile_node: {e}")
            return {}

    async def initialize(self) -> None:
        """Initialize all components."""
        await self.rag_memory.initialize_database()
        await self.user_profile_manager.initialize_database()
        await self.bot_interaction_tracker.initialize_database()
        logger.info("Agent initialized successfully")

    def _process_tool_results(
        self, messages: list[BaseMessage], state: AgentState
    ) -> Optional[BotResponse]:
        """Process messages and build a structured BotResponse."""

        response = BotResponse(text="")

        # Get the final AI message content
        for message in reversed(messages):
            if hasattr(message, "content") and isinstance(message.content, str):
                if hasattr(message, "tool_calls") and message.tool_calls:
                    continue

                response.text = message.content
                break

        # Look for ToolMessages with artifacts (like images)
        for message in messages:
            if hasattr(message, "artifact") and message.artifact:
                artifact = message.artifact
                if artifact.get("type") == "image":
                    response.add_file(
                        content=artifact["data"],
                        filename=artifact["filename"],
                        description="Generated image",
                    )

        # If there's no text content, don't send a message
        if not response.text or not response.text.strip():
            return None

        return response

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        channel_id: str,
        discord_client: Optional[discord.Member] = None,
        guild_id: Optional[str] = None,
    ) -> Optional[BotResponse]:
        """Process a message through the LangGraph agent."""
        try:
            # Set Discord context for tools
            if discord_client:
                set_discord_context(discord_client, guild_id)

            # Create initial state
            initial_state = AgentState(
                messages=[HumanMessage(content=user_message)],
                user_id=user_id,
                channel_id=channel_id,
                user_profile={},
                context_messages=[],
                discord_client=discord_client,
                guild_id=guild_id,
            )

            # Run the graph
            result = await self.graph.ainvoke(initial_state)

            # Process the messages and build structured response
            final_messages = result.get("messages", [])
            return self._process_tool_results(final_messages, result)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None

    async def close(self) -> None:
        """Close all components."""
        await self.rag_memory.close()
        await self.user_profile_manager.close()
        await self.bot_interaction_tracker.close()
