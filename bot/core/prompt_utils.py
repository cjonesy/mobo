"""
Shared utilities for building prompts with personality and user context.

This module eliminates duplication between workflow nodes that need to load
bot personality and user profile information.
"""

import logging
from typing import Tuple

from ..config import get_settings

logger = logging.getLogger(__name__)


async def load_personality_and_user_context(memory_system, user_id: str) -> Tuple[str, str]:
    """
    Load bot personality and user context for prompt building.
    
    Args:
        memory_system: LangGraph memory system with store access
        user_id: Discord user ID
        
    Returns:
        Tuple of (personality, profile_text)
    """
    # Load bot personality
    settings = get_settings()
    personality = await settings.get_personality_prompt()

    # Load user profile from LangGraph store
    user_profile = await memory_system.get_user_profile(user_id)

    # Build user context text
    profile_text = f"User '{user_profile.get('display_name', 'Unknown')}' - Response tone: {user_profile.get('response_tone', 'neutral')}"
    if user_profile.get("likes"):
        profile_text += f", Likes: {', '.join(user_profile['likes'][:3])}"
    if user_profile.get("dislikes"):
        profile_text += f", Dislikes: {', '.join(user_profile['dislikes'][:3])}"

    return personality, profile_text