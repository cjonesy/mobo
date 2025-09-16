"""
User context learning node for the LangGraph workflow.

This node analyzes the conversation and uses an LLM to determine if the bot
should adjust its interaction strategy with the user based on observed behavior,
tone, and patterns.
"""

import logging
import json
import textwrap

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .state import BotState
from ..config import settings
from ..services import UserService
from ..db import get_session_maker

logger = logging.getLogger(__name__)


async def learn_user_context_node(state: BotState) -> BotState:
    """
    Analyze conversation and update bot's interaction strategy if needed.

    This node examines the user's message, conversation context, and tool results
    to determine if the bot should adapt its communication style, interaction approach,
    or user trait observations.
    """
    logger.info("🧠 Analyzing conversation for interaction strategy learning")

    try:
        user_id = state.get("user_id", "")
        user_message = state.get("user_message", "")
        conversation_context = state.get("conversation_context", [])
        current_user_context = state.get("user_context", {})

        # Skip learning if we don't have essential information
        if not user_id or not user_message:
            logger.debug("🧠 Skipping context learning - missing user_id or message")
            return state

        # Create analysis prompt
        system_prompt_template = textwrap.dedent(
            """
            You are analyzing a Discord conversation to help a bot adapt its interaction strategy.
            Your job is to determine if the bot should update its approach with this specific user.

            CURRENT BOT STRATEGY:
            - Response Tone: {response_tone}
            - User Likes: {user_likes}
            - User Dislikes: {user_dislikes}

            CONVERSATION CONTEXT:
            {conversation_context}

            CURRENT USER MESSAGE:
            {user_message}

            ANALYSIS GUIDELINES:
            - Look for patterns in user behavior, tone, communication preferences
            - Consider if the user is being rude, friendly, formal, casual, technical, etc.
            - Assess if the bot should adjust its response tone or learn new likes/dislikes
            - Only suggest changes if there's clear evidence from the conversation
            - Be conservative - don't change based on single messages unless very clear

            Respond with ONLY a JSON object in this exact format:
            {{
                "should_update": true/false,
                "response_tone": "tone if changed, null if no change",
                "new_likes": ["list of new things user seems to like"] or null,
                "new_dislikes": ["list of new things user seems to dislike"] or null,
                "reasoning": "brief explanation of why changes were made"
            }}

            For response_tone, use whatever tone best matches how the bot should
            interact with this specific user based on their behavior.

            Be natural and realistic about Discord communication patterns.
            """
        ).strip()

        # Format conversation context for analysis
        def format_context_for_analysis(context_messages):
            if not context_messages:
                return "No previous conversation history available."

            formatted_parts = []
            for msg in context_messages[-10:]:  # Only use last 10 messages
                role = "User" if msg.get("role") == "user" else "Bot"
                content = msg.get("content", "")
                formatted_parts.append(f"{role}: {content}")

            return "\n".join(formatted_parts)

        conversation_context_text = format_context_for_analysis(conversation_context)

        # Use configured model for context analysis
        llm = ChatOpenAI(
            model=settings.context_learning_llm.model,
            temperature=settings.context_learning_llm.temperature,
            api_key=settings.openrouter.api_key,
            base_url=settings.openrouter.base_url,
        )

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt_template),
            ]
        )

        # Create the chain and analyze
        chain = prompt_template | llm
        response = await chain.ainvoke(
            {
                "response_tone": current_user_context.get("response_tone", "neutral"),
                "user_likes": ", ".join(current_user_context.get("likes", []))
                or "None known",
                "user_dislikes": ", ".join(current_user_context.get("dislikes", []))
                or "None known",
                "conversation_context": conversation_context_text,
                "user_message": user_message,
            }
        )

        # Parse LLM response
        try:
            # Handle both string and list content types
            if isinstance(response.content, str):
                analysis_text = response.content.strip()
            else:
                analysis_text = str(response.content).strip()

            # Extract JSON from response (in case there's extra text)
            if "```json" in analysis_text:
                json_start = analysis_text.find("```json") + 7
                json_end = analysis_text.find("```", json_start)
                analysis_text = analysis_text[json_start:json_end].strip()
            elif analysis_text.startswith("```") and analysis_text.endswith("```"):
                analysis_text = analysis_text[3:-3].strip()

            analysis = json.loads(analysis_text)
            logger.debug(f"🧠 LLM analysis: {analysis}")

        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"🧠 Failed to parse LLM analysis response: {e}")
            logger.debug(f"🧠 Raw response: {response.content}")
            return state

        # Apply updates if the LLM determined they're needed
        if analysis.get("should_update", False):
            try:
                session_maker = get_session_maker()
                user_service = UserService()

                async with session_maker() as session:
                    updates_made = []

                    # Update response tone if changed
                    if analysis.get("response_tone"):
                        await user_service.update_user_preferences(
                            session, user_id, response_tone=analysis["response_tone"]
                        )
                        updates_made.append("response_tone")
                        logger.debug(
                            f"🧠 Updated response tone to {analysis['response_tone']}"
                        )

                    # Add new likes if identified
                    if analysis.get("new_likes"):
                        for like_term in analysis["new_likes"]:
                            await user_service.add_like(
                                session,
                                user_id,
                                like_term,
                                confidence=0.7,
                                source="conversation_analysis",
                            )
                        updates_made.append("likes")
                        logger.debug(f"🧠 Added likes: {analysis['new_likes']}")

                    # Add new dislikes if identified
                    if analysis.get("new_dislikes"):
                        for dislike_term in analysis["new_dislikes"]:
                            await user_service.add_dislike(
                                session,
                                user_id,
                                dislike_term,
                                confidence=0.7,
                                source="conversation_analysis",
                            )
                        updates_made.append("dislikes")
                        logger.debug(f"🧠 Added dislikes: {analysis['new_dislikes']}")

                if updates_made:
                    logger.info(
                        f"🧠 Updated user context for {user_id}: {updates_made}"
                    )
                    logger.debug(
                        f"🧠 Reasoning: {analysis.get('reasoning', 'No reasoning provided')}"
                    )

                    # Refresh user context in state
                    async with session_maker() as session:
                        updated_context = await user_service.get_user_context_for_bot(
                            session, user_id
                        )
                        state["user_context"] = updated_context
                else:
                    logger.debug(
                        "🧠 LLM suggested update but no specific changes provided"
                    )

            except Exception as e:
                logger.error(f"🧠 Failed to update user context: {e}")
        else:
            logger.debug("🧠 No context updates needed based on current conversation")

        return state

    except Exception as e:
        logger.exception(f"❌ Error in learn_user_context_node: {e}")
        return state
