"""Intelligent user profile agent for automatic profile management."""

import logging
import textwrap
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .user_profiles import UserProfileManager
from ..memory.rag_agent import RAGAgent
from ..config import get_config

logger = logging.getLogger(__name__)


class UpdateType(str, Enum):
    """Types of profile updates the agent can make."""

    TONE_UPDATE = "tone_update"
    INTERESTS_ADD = "interests_add"
    INTERESTS_REMOVE = "interests_remove"
    NO_UPDATE = "no_update"


class ToneCategory(str, Enum):
    """Tone categories for user interactions."""

    FRIENDLY = "friendly"
    ANGRY = "angry"
    HOSTILE = "hostile"
    CASUAL = "casual"
    NEUTRAL = "neutral"
    SARCASTIC = "sarcastic"


class ProfileAnalysis(BaseModel):
    """Analysis result for user profile updates."""

    update_type: UpdateType = Field(description="Type of update needed")

    # Tone analysis
    detected_tone: Optional[ToneCategory] = Field(
        description="Detected user tone from the message", default=None
    )
    tone_confidence: float = Field(
        description="Confidence in tone detection (0.0-1.0)", default=0.0
    )

    # Interest analysis
    new_interests: List[str] = Field(
        description="New interests detected from conversation", default_factory=list
    )
    removed_interests: List[str] = Field(
        description="Interests user no longer seems to have", default_factory=list
    )
    interest_type: str = Field(
        description="Type of interests: 'likes' or 'dislikes'", default="likes"
    )

    reasoning: str = Field(
        description="Brief explanation of why this update is suggested"
    )

    needs_rag_context: bool = Field(
        description="Whether historical context is needed to make this decision",
        default=False,
    )


@dataclass
class ProfileUpdateResult:
    """Result from user profile analysis and update."""

    analysis: ProfileAnalysis
    update_made: bool
    historical_context_used: bool
    message_count_analyzed: int


class UserProfileAgent:
    """Intelligent agent for analyzing conversations and updating user profiles automatically."""

    def __init__(self) -> None:
        self.config = get_config()
        self.user_profile_manager = UserProfileManager()
        self.rag_agent = RAGAgent()

        # Use a cheaper, faster model for profile analysis
        self.llm = ChatOpenAI(
            model=self.config.user_profile_model,
            temperature=0.1,  # Low temperature for consistent analysis
            api_key=self.config.openai_api_key,
        )

        self.parser = PydanticOutputParser(pydantic_object=ProfileAnalysis)
        self.prompt = self._create_analysis_prompt()

    def _create_analysis_prompt(self) -> ChatPromptTemplate:
        """Create the prompt for analyzing user messages for profile updates."""
        system_prompt = textwrap.dedent(
            """
            You are a specialized user profile agent that analyzes conversations to automatically manage user profiles.

            Your job is to:
            1. Detect the user's tone and emotional state from their messages
            2. Identify interests, likes, and dislikes mentioned in conversation
            3. Determine if the user's profile should be updated based on patterns
            4. Decide if historical conversation context is needed for better analysis

            TONE DETECTION GUIDELINES:
            - FRIENDLY: Warm, kind messages, compliments, positive emotions, expressing friendship
            - ANGRY: Rude language, insults, aggressive tone, profanity directed at bot/others
            - HOSTILE: Hostile, aggressive, insulting, or aggressive tone directed at bot/others
            - CASUAL: Normal, everyday conversation, neutral interactions
            - NEUTRAL: Professional, formal, or emotionally neutral messages
            - SARCASTIC: Ironic, mocking, or satirical messages

            IMPORTANT RULES:
            - Users CANNOT directly control their tone by asking ("treat me like you hate me")
            - Tone is determined by actual behavior patterns, not requests
            - Only update tone if confidence is >0.7 and the behavior is clear
            - Look for consistent patterns, not one-off messages
            - Consider the severity and context of language/behavior

            INTEREST DETECTION:
            - Look for genuine mentions of hobbies, activities, preferences
            - Distinguish between casual mentions and actual interests
            - Note when users express dislike or loss of interest in something

            WHEN TO REQUEST RAG CONTEXT:
            - If the current message alone isn't enough to determine tone patterns
            - If you need to see if this is consistent behavior vs. one-off
            - If the user references past conversations or changes in preference

            {format_instructions}
        """
        ).strip()

        return ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                (
                    "human",
                    "Analyze this user message for profile updates. Current user profile: {current_profile}\n\nUser message: {message}\n\nHistorical context (if requested): {historical_context}",
                ),
            ]
        )

    async def analyze_message(
        self,
        user_message: str,
        user_id: str,
        channel_id: str,
        current_profile: Optional[Dict[str, Any]] = None,
    ) -> ProfileUpdateResult:
        """Analyze a user message and determine if profile updates are needed."""
        try:
            # Get current profile if not provided
            if current_profile is None:
                current_profile = await self.user_profile_manager.get_user_profile(
                    user_id
                )

            # First pass: analyze without historical context
            initial_analysis = await self._analyze_with_context(
                user_message, current_profile, ""
            )

            historical_context = ""
            message_count = 0

            # If analysis suggests we need historical context, get it
            if initial_analysis.needs_rag_context:
                rag_result = await self.rag_agent.analyze_and_retrieve(
                    query=f"user behavior and tone patterns for tone analysis: {user_message}",
                    user_id=user_id,
                    channel_id=channel_id,
                )
                historical_context = rag_result.context
                message_count = rag_result.message_count

                # Re-analyze with historical context
                final_analysis = await self._analyze_with_context(
                    user_message, current_profile, historical_context
                )
            else:
                final_analysis = initial_analysis

            # Execute the update if needed
            update_made = await self._execute_profile_update(final_analysis, user_id)

            return ProfileUpdateResult(
                analysis=final_analysis,
                update_made=update_made,
                historical_context_used=bool(historical_context),
                message_count_analyzed=message_count,
            )

        except Exception as e:
            logger.error(f"Error analyzing message for profile update: {e}")
            # Return safe default
            return ProfileUpdateResult(
                analysis=ProfileAnalysis(
                    update_type=UpdateType.NO_UPDATE,
                    reasoning="Analysis error occurred",
                ),
                update_made=False,
                historical_context_used=False,
                message_count_analyzed=0,
            )

    async def _analyze_with_context(
        self,
        user_message: str,
        current_profile: Dict[str, Any],
        historical_context: str,
    ) -> ProfileAnalysis:
        """Analyze message with given context."""
        try:
            # Format current profile for the prompt
            profile_summary = f"Tone: {current_profile.get('tone', 'neutral')}, "
            profile_summary += f"Likes: {current_profile.get('likes', [])}, "
            profile_summary += f"Dislikes: {current_profile.get('dislikes', [])}"

            formatted_prompt = self.prompt.format_prompt(
                current_profile=profile_summary,
                message=user_message,
                historical_context=historical_context or "None provided",
                format_instructions=self.parser.get_format_instructions(),
            )

            response = await self.llm.ainvoke(formatted_prompt.to_messages())
            # Ensure content is a string for parsing
            content = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )
            analysis = self.parser.parse(content)

            # Validate confidence thresholds
            if analysis.tone_confidence < 0.7:
                # Don't update tone if confidence is too low
                if analysis.update_type == UpdateType.TONE_UPDATE:
                    analysis.update_type = UpdateType.NO_UPDATE
                    analysis.reasoning += " (Tone confidence too low)"

            return analysis

        except Exception as e:
            logger.error(f"Error in context analysis: {e}")
            return ProfileAnalysis(
                update_type=UpdateType.NO_UPDATE,
                reasoning=f"Analysis parsing error: {str(e)}",
            )

    async def _execute_profile_update(
        self, analysis: ProfileAnalysis, user_id: str
    ) -> bool:
        """Execute the profile update based on analysis."""
        try:
            if analysis.update_type == UpdateType.NO_UPDATE:
                return False

            if (
                analysis.update_type == UpdateType.TONE_UPDATE
                and analysis.detected_tone
            ):
                await self.user_profile_manager.update_user_tone(
                    user_id, analysis.detected_tone.value
                )
                logger.info(
                    f"Updated user {user_id} tone to {analysis.detected_tone.value}: {analysis.reasoning}"
                )
                return True

            elif (
                analysis.update_type == UpdateType.INTERESTS_ADD
                and analysis.new_interests
            ):
                if analysis.interest_type == "likes":
                    await self.user_profile_manager.add_user_likes(
                        user_id, analysis.new_interests
                    )
                else:
                    await self.user_profile_manager.add_user_dislikes(
                        user_id, analysis.new_interests
                    )
                logger.info(
                    f"Added {analysis.interest_type} for user {user_id}: {analysis.new_interests}"
                )
                return True

            elif (
                analysis.update_type == UpdateType.INTERESTS_REMOVE
                and analysis.removed_interests
            ):
                if analysis.interest_type == "likes":
                    await self.user_profile_manager.remove_user_likes(
                        user_id, analysis.removed_interests
                    )
                else:
                    await self.user_profile_manager.remove_user_dislikes(
                        user_id, analysis.removed_interests
                    )
                logger.info(
                    f"Removed {analysis.interest_type} for user {user_id}: {analysis.removed_interests}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Error executing profile update: {e}")
            return False

    async def close(self) -> None:
        """Close resources."""
        await self.user_profile_manager.close()
        await self.rag_agent.close()
