"""
Helper functions for building prompts and context strings.

This module contains shared utilities for formatting user context,
conversation history, and other prompt components.
"""

from typing import Dict, Any


def build_user_context_text(user_profile: Dict[str, Any]) -> str:
    """
    Build user context text from user profile data.

    Args:
        user_profile: User profile dictionary

    Returns:
        Formatted user context string
    """
    profile_text = f"User '{user_profile.get('display_name', 'Unknown')}' - Response tone: {user_profile.get('response_tone', 'neutral')}"
    if user_profile.get("likes"):
        profile_text += f", Likes: {', '.join(user_profile['likes'])}"
    if user_profile.get("dislikes"):
        profile_text += f", Dislikes: {', '.join(user_profile['dislikes'])}"
    return profile_text
