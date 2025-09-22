"""
Giphy-powered tools for GIF search and sharing.

This module contains tools that use the Giphy API for finding and sharing
animated GIFs and other Giphy content.
"""

import logging
import aiohttp
from typing import Tuple, Dict

from ..config import settings
from .common import tool

logger = logging.getLogger(__name__)


@tool
async def search_gif(query: str, limit: int = 1) -> Tuple[str, Dict]:
    """
    Searches for a GIF using the Giphy API and returns it as an attachment.

    Finds animated GIFs from Giphy's database based on search terms,
    returning both content and artifact data for display in Discord.
    The GIF will be automatically uploaded and displayed - do NOT try to
    create manual links or use Discord markdown syntax with the URL.

    Examples: Adding humor to conversations, expressing emotions with animation,
    reacting to funny moments, celebrating events, showing enthusiasm.

    Args:
        query: Search query for the GIF
        limit: Maximum number of results (default 1)

    Returns:
        Tuple of (content_text, gif_artifact) - GIF uploads automatically
    """
    logger.info("⚒️ Calling search_gif", extra={"query": query, "limit": limit})
    try:
        api_key = settings.giphy.api_key.get_secret_value()

        # Build Giphy API URL
        base_url = "https://api.giphy.com/v1/gifs/search"
        params: dict[str, str | int] = {
            "api_key": api_key,
            "q": query,
            "limit": limit,
            "lang": "en",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status != 200:
                    raise ValueError(f"Giphy API error: {response.status}")

                data = await response.json()

        # Extract GIF data
        if not data.get("data"):
            raise ValueError(f"No GIFs found for '{query}'")

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
