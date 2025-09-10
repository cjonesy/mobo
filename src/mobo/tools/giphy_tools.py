"""
Giphy-powered tools for GIF search and sharing.

This module contains tools that use the Giphy API for finding and sharing
animated GIFs and other Giphy content.
"""

import logging
import aiohttp
from typing import Tuple, Dict

from ..config import get_settings
from .common import registered_tool

logger = logging.getLogger(__name__)


def get_giphy_api_key() -> str:
    """Get Giphy API key."""
    settings = get_settings()

    if not settings.giphy.api_key:
        raise ValueError("Giphy API key not configured")

    return settings.giphy.api_key.get_secret_value()


@registered_tool(response_format="content_and_artifact")
async def search_gif(query: str, limit: int = 1) -> Tuple[str, Dict]:
    """
    Search for a GIF using the Giphy API and return it as an attachment.

    Use this tool when you feel like a GIF would be a good addition to your conversation.

    Args:
        query: Search query for the GIF
        limit: Maximum number of results (default 1)

    Returns:
        Tuple of (content_text, gif_artifact)
    """
    try:
        api_key = get_giphy_api_key()

        logger.info(f"🔍 Searching for GIF: {query}")

        # Build Giphy API URL
        base_url = "https://api.giphy.com/v1/gifs/search"
        params: dict[str, str | int] = {
            "api_key": api_key,
            "q": query,
            "limit": limit,
            "rating": "pg-13",  # Keep it appropriate
            "lang": "en",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status != 200:
                    raise ValueError(f"Giphy API error: {response.status}")

                data = await response.json()

        # Extract GIF data
        if not data.get("data"):
            logger.info(f"No GIFs found for '{query}'")
            return f"Sorry, I couldn't find any GIFs for '{query}'", {}

        gif_data = data["data"][0]
        gif_url = gif_data["images"]["original"]["url"]
        gif_title = gif_data.get("title", "GIF")

        logger.info(f"✅ Found GIF: {gif_url}")

        # Return content for LLM + structured artifact for Discord handler
        content = f"Here's a GIF for '{query}'!"
        artifact = {
            "type": "image",
            "url": gif_url,
            "should_upload": True,
            "extension": ".gif",
            "filename": f"{gif_title.replace(' ', '_')[:30]}.gif",
        }

        return content, artifact

    except Exception as e:
        logger.error(f"❌ GIF search failed for query '{query}': {e}")
        return f"Sorry, I encountered an error searching for GIFs: {str(e)}", {}
