"""Discord bot agent using LangChain AgentExecutor."""

import logging
import textwrap
from typing import Optional, Dict, Any, IO

import discord
import httpx
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from pydantic import SecretStr

from ..config import get_config
from ..prompts import create_simple_discord_bot_prompt
from ..tools import get_all_tools, set_discord_context
from ..memory import RAGMemory, RAGAgent
from ..agent.user_profiles import UserProfileManager
from ..agent.user_profile_agent import UserProfileAgent
from ..agent.bot_interaction_tracker import BotInteractionTracker
from ..agent.types import BotResponse

logger = logging.getLogger(__name__)


class DiscordAgent:
    """Discord bot agent using LangChain for workflow orchestration."""

    def __init__(self) -> None:
        self.config = get_config()
        self.rag_memory = RAGMemory()
        self.rag_agent = RAGAgent()
        self.user_profile_manager = UserProfileManager()
        self.user_profile_agent = UserProfileAgent()
        self.bot_interaction_tracker = BotInteractionTracker()

        self.tools = get_all_tools()
        # TODO: Why aren't we using the full prompt?
        self.prompt = create_simple_discord_bot_prompt()

        # Initialize LLM and agent
        self._initialize_llm()

    def _initialize_llm(self) -> None:
        """Initialize or reinitialize the LLM with current config."""
        api_key_str = self.config.openrouter_api_key.get_secret_value()
        api_key_secret = SecretStr(api_key_str)

        self.llm = ChatOpenAI(
            model=self.config.openai_model,
            temperature=self.config.openai_temperature,
            api_key=api_key_secret,
            base_url=self.config.openrouter_base_url,
        )

        # Recreate agent with new LLM
        self.agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=self.config.verbose_logging,
            handle_parsing_errors=True,
            max_iterations=3,
            return_intermediate_steps=True,
        )

    async def change_model(self, new_model: str) -> str:
        """Change the model and reinitialize the agent.

        Args:
            new_model: The new model identifier to use

        Returns:
            A message indicating success or failure
        """
        try:
            old_model = self.config.openai_model
            self.config.openai_model = new_model
            self._initialize_llm()
            logger.info(f"Successfully changed model from {old_model} to {new_model}")
            return f"Successfully changed model from {old_model} to {new_model}"
        except Exception as e:
            self.config.openai_model = old_model  # Revert on failure
            self._initialize_llm()
            logger.error(f"Failed to change model: {e}")
            return f"Failed to change model: {str(e)}"

    async def _get_context_and_profile(
        self, user_message: str, user_id: str, channel_id: str
    ) -> tuple[dict[str, Any], str]:
        """Get user profile and RAG context for the conversation."""
        try:
            # Get user profile
            user_profile = await self.user_profile_manager.get_user_profile(user_id)

            # Use the intelligent RAG agent to analyze and retrieve context
            rag_result = await self.rag_agent.analyze_and_retrieve(
                query=user_message, user_id=user_id, channel_id=channel_id
            )

            logger.debug(
                f"RAG strategy: {rag_result.strategy_used.query_type}, "
                f"threshold: {rag_result.strategy_used.similarity_threshold}, "
                f"messages: {rag_result.message_count}, "
                f"reasoning: {rag_result.strategy_used.reasoning}"
            )

            return user_profile, rag_result.context

        except Exception as e:
            logger.error(f"Error getting context and profile: {e}")
            return {}, ""

    async def _build_system_prompt(
        self, user_profile: dict[str, Any], rag_context: str
    ) -> str:
        """Build the system prompt with personality, profile, and context."""
        try:
            prompt = textwrap.dedent(
                f"""
                -- General Instructions --
                Default to concise.
                Prefer human-like conversational text over bullets.
                Never include preambles or disclaimers unless asked.

                -- Personality --
                Your personality is as follows:
                  {await self.config.get_resolved_personality_prompt()}

                -- User Profile --
                The profile of the user you are interacting with is as follows:
                  {self.user_profile_manager.format_profile_for_prompt(user_profile)}

                -- RAG Context --
                The context of the conversation is as follows:
                  {rag_context}

                -- Tone --
                CRITICAL: This user's behavior has earned them a {user_profile.get("tone", "neutral")} response. You MUST respond with {user_profile.get("tone", "neutral")} energy - be {user_profile.get("tone", "neutral")} first, then apply your personality to that {user_profile.get("tone", "neutral")} base.

                -- Response Length --
                IMPORTANT: NEVER respond with more than 2000 characters.
                """
            )

            return prompt

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
        temp_file: Optional[IO[bytes]] = None,
        client_user: Optional[discord.ClientUser] = None,
    ) -> Optional[BotResponse]:
        """Process a message through the LangChain agent."""
        try:
            # Set Discord context for tools
            if discord_client:
                set_discord_context(
                    discord_client, guild_id, channel_id, user_id, client_user
                )

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
            logger.info(f"Running agent...")
            result = await self.agent_executor.ainvoke(agent_input)

            # Process the result
            logger.info(f"Processing agent output...")
            response = await self._process_agent_output(result)

            if response:
                # Store the conversation
                await self._store_conversation(
                    user_message, response.text, user_id, channel_id
                )

                # Asynchronously analyze user profile for potential updates
                # This runs in the background and doesn't block the response
                try:
                    profile_result = await self.user_profile_agent.analyze_message(
                        user_message, user_id, channel_id, user_profile
                    )

                    if profile_result.update_made:
                        logger.info(
                            f"Profile updated for user {user_id}: {profile_result.analysis.reasoning}"
                        )
                    else:
                        logger.debug(
                            f"No profile update needed for user {user_id}: {profile_result.analysis.reasoning}"
                        )

                except Exception as e:
                    logger.error(f"Error in background profile analysis: {e}")
                    # Don't let profile analysis errors affect the main response

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
        await self.rag_agent.close()
        await self.user_profile_manager.close()
        await self.user_profile_agent.close()
        await self.bot_interaction_tracker.close()
