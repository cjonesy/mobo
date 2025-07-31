"""Discord bot agent using LangChain AgentExecutor."""

import logging
import tempfile
from tempfile import NamedTemporaryFile
from typing import Optional, Dict, Any

import discord
import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from pydantic import SecretStr

from ..config import get_config
from ..prompts import create_simple_discord_bot_prompt
from ..tools import get_all_tools, set_discord_context
from ..memory import RAGMemory
from ..agent.user_profiles import UserProfileManager
from ..agent.bot_interaction_tracker import BotInteractionTracker
from ..agent.types import BotResponse

logger = logging.getLogger(__name__)


class DiscordAgent:
    """Discord bot agent using LangChain for workflow orchestration."""

    def __init__(self) -> None:
        self.config = get_config()
        self.rag_memory = RAGMemory()
        self.user_profile_manager = UserProfileManager()
        self.bot_interaction_tracker = BotInteractionTracker()

        api_key_str = self.config.openai_api_key.get_secret_value()
        api_key_secret = SecretStr(api_key_str)

        self.llm = ChatOpenAI(
            model=self.config.openai_model,
            temperature=self.config.openai_temperature,
            api_key=api_key_secret,
        )

        self.tools = get_all_tools()
        self.prompt = create_simple_discord_bot_prompt()

        self.agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)

        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=self.config.verbose_logging,
            handle_parsing_errors=True,
            max_iterations=3,
            return_intermediate_steps=True,
            handle_tool_error=True,
        )

    async def _get_context_and_profile(
        self, user_message: str, user_id: str, channel_id: str
    ) -> tuple[dict[str, Any], str]:
        """Get user profile and RAG context for the conversation."""
        try:
            user_profile = await self.user_profile_manager.get_user_profile(user_id)

            similar_messages = await self.rag_memory.get_similar_messages(
                query=user_message,
                channel_id=channel_id,
                limit=self.config.top_k_memory_results,
            )

            recent_messages = await self.rag_memory.get_recent_messages(
                channel_id=channel_id, limit=10
            )

            # Format RAG context
            context_messages = similar_messages + recent_messages
            rag_context = ""
            if context_messages:
                rag_context = "Recent conversation context:\n"
                for msg in context_messages[-self.config.max_context_messages :]:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:200]  # Truncate long messages
                    rag_context += f"- {role}: {content}\n"

            logger.debug(
                f"Retrieved {len(similar_messages)} similar messages and {len(recent_messages)} recent messages"
            )

            return user_profile, rag_context

        except Exception as e:
            logger.error(f"Error getting context and profile: {e}")
            return {}, ""

    async def _build_system_prompt(
        self, user_profile: dict[str, Any], rag_context: str
    ) -> str:
        """Build the system prompt with personality, profile, and context."""
        try:
            personality_prompt = await self.config.get_resolved_personality_prompt()

            # Add user profile context if available
            profile_context = ""
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

            # Combine all parts
            system_prompt = f"{personality_prompt}{profile_context}"
            if rag_context:
                system_prompt += f"\n{rag_context}"

            return system_prompt

        except Exception as e:
            logger.error(f"Error building system prompt: {e}")
            return "You are a helpful Discord bot assistant."

    async def _process_agent_output(
        self, result: Dict[str, Any]
    ) -> Optional[BotResponse]:
        """Process agent output and build a structured BotResponse."""
        try:
            output = result.get("output", "")

            if not output or not output.strip():
                return None

            response = BotResponse(text=output)

            # Check for any tool artifacts in intermediate steps
            intermediate_steps = result.get("intermediate_steps", [])
            for step in intermediate_steps:
                if len(step) >= 2:
                    tool_output = step[1]
                    if isinstance(tool_output, dict) and tool_output.get("url"):
                        # Download and save image from URL
                        async with httpx.AsyncClient() as client:
                            image_response = await client.get(tool_output["url"])
                            if image_response.status_code == 200:
                                # Just return the URL in the response
                                response.add_file(
                                    url=tool_output["url"],
                                    description="Generated image",
                                )

            return response

        except Exception as e:
            logger.error(f"Error processing agent output: {e}")
            return None

    async def _store_conversation(
        self, user_message: str, bot_response: str, user_id: str, channel_id: str
    ) -> None:
        """Store the conversation in RAG memory."""
        try:
            # Store user message
            await self.rag_memory.store_message(
                user_id=user_id,
                channel_id=channel_id,
                role="user",
                content=user_message,
            )

            # Store bot response
            await self.rag_memory.store_message(
                user_id=user_id,
                channel_id=channel_id,
                role="assistant",
                content=bot_response,
            )

        except Exception as e:
            logger.error(f"Error storing conversation: {e}")

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        channel_id: str,
        discord_client: Optional[discord.Member] = None,
        guild_id: Optional[str] = None,
        temp_file: Optional[NamedTemporaryFile] = None,
    ) -> Optional[BotResponse]:
        """Process a message through the LangChain agent."""
        try:
            # Set Discord context for tools
            if discord_client:
                set_discord_context(discord_client, guild_id, channel_id)

            # Get context and user profile
            user_profile, rag_context = await self._get_context_and_profile(
                user_message, user_id, channel_id
            )

            # Build system prompt
            system_prompt = await self._build_system_prompt(user_profile, rag_context)

            # Prepare input for the agent
            agent_input = {
                "input": user_message,
                "system_prompt": system_prompt,
            }

            # Run the agent
            result = await self.agent_executor.ainvoke(agent_input)

            # Process the result
            response = await self._process_agent_output(result)

            if response:
                # Store the conversation
                await self._store_conversation(
                    user_message, response.text, user_id, channel_id
                )

            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None

    async def initialize(self) -> None:
        """Initialize all components."""
        await self.rag_memory.initialize_database()
        await self.user_profile_manager.initialize_database()
        await self.bot_interaction_tracker.initialize_database()
        logger.info("Discord agent initialized successfully")

    async def close(self) -> None:
        """Close all components."""
        await self.rag_memory.close()
        await self.user_profile_manager.close()
        await self.bot_interaction_tracker.close()
