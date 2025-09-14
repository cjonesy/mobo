"""
Web search tools using Google Custom Search API.

This module contains tools that use the Google Custom Search API to search
the web and return relevant results.
"""

import logging
from typing import Optional
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from ..config import get_settings
from .common import registered_tool
from ..utils.rate_limiting import rate_limited

logger = logging.getLogger(__name__)


def get_google_custom_search_api_key() -> str:
    """Get Google Custom Search API key."""
    settings = get_settings()

    if not settings.google_search.api_key:
        raise ValueError("Google Custom Search API key not configured")

    return settings.google_search.api_key.get_secret_value()


def get_google_cse_id() -> str:
    """Get Google Custom Search Engine ID."""
    settings = get_settings()

    if not settings.google_search.cse_id:
        raise ValueError("Google Custom Search Engine ID not configured")

    return settings.google_search.cse_id


async def _search_web_impl(
    query: str,
    num_results: int = 5,
    search_type: Optional[str] = None,
    safe_search: str = "active",
) -> str:
    """
    Internal implementation of web search.

    Args:
        query: Search query string
        num_results: Number of results to return (1-10, default 5)
        search_type: Optional search type ("image" for image search)
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        Formatted string containing search results with titles, URLs, and snippets
    """
    try:
        api_key = get_google_custom_search_api_key()
        cse_id = get_google_cse_id()

        logger.info(f"🔍 Searching web for: {query}")

        # Build the Google Custom Search API service
        service = build("customsearch", "v1", developerKey=api_key)

        # Prepare search parameters
        search_params = {
            "q": query,
            "cx": cse_id,
            "num": min(num_results, 10),  # API limit is 10
            "safe": safe_search,
        }

        # Add search type if specified
        if search_type:
            search_params["searchType"] = search_type

        # Execute the search
        result = service.cse().list(**search_params).execute()

        # Check if we got results
        if "items" not in result:
            logger.info(f"No search results found for '{query}'")
            return (
                f"No search results found for '{query}'. Try a different search term."
            )

        # Format the results
        formatted_results = []
        formatted_results.append(f"Search results for '{query}':\n")

        for i, item in enumerate(result["items"], 1):
            title = item.get("title", "No title")
            link = item.get("link", "")
            snippet = item.get("snippet", "No description available")

            formatted_results.append(f"{i}. **{title}**")
            formatted_results.append(f"   {link}")
            formatted_results.append(f"   {snippet}")
            formatted_results.append("")  # Empty line for spacing

        # Add search metadata
        search_info = result.get("searchInformation", {})
        total_results = search_info.get("totalResults", "unknown")
        search_time = search_info.get("searchTime", "unknown")

        formatted_results.append(
            f"Found {total_results} results in {search_time} seconds"
        )

        result_text = "\n".join(formatted_results)
        logger.info(f"✅ Web search completed: {len(result['items'])} results")

        return result_text

    except HttpError as e:
        error_msg = f"Google API error: {e.status_code} - {e.error_details}"
        logger.error(f"❌ Web search failed: {error_msg}")
        return f"Search failed due to API error: {error_msg}"

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return f"Search unavailable: {str(e)}"

    except Exception as e:
        logger.error(f"❌ Unexpected error during web search: {e}")
        return f"Search failed due to unexpected error: {str(e)}"


@registered_tool()
@rate_limited(resource="google-search", max_requests=100, period="day")
async def search_web(
    query: str,
    num_results: int = 5,
    search_type: Optional[str] = None,
    safe_search: str = "active",
) -> str:
    """
    Search the web using Google Custom Search API and return formatted results.

    Use this tool when you need to find current information about topics, news,
    or anything that requires up-to-date web search results.

    Args:
        query: Search query string
        num_results: Number of results to return (1-10, default 5)
        search_type: Optional search type ("image" for image search)
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        Formatted string containing search results with titles, URLs, and snippets
    """
    try:
        logger.info(f"🔍 Web search called with query: {query}")
        result = await _search_web_impl(query, num_results, search_type, safe_search)
        logger.info(f"🔍 Web search result length: {len(result)}")
        return result
    except ValueError as e:
        # Configuration errors
        logger.error(f"❌ Web search configuration error: {e}")
        return f"❌ Web search unavailable: {str(e)}. Please configure GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID environment variables."
    except Exception as e:
        logger.error(f"❌ Web search error: {e}")
        return f"❌ Web search failed: {str(e)}"


async def _search_images_impl(
    query: str,
    num_results: int = 3,
    image_size: Optional[str] = None,
    image_type: Optional[str] = None,
    safe_search: str = "active",
) -> str:
    """
    Internal implementation of image search.

    Args:
        query: Image search query string
        num_results: Number of image results to return (1-10, default 3)
        image_size: Image size filter ("small", "medium", "large", "xlarge", "xxlarge", "huge")
        image_type: Image type filter ("clipart", "face", "lineart", "stock", "photo", "animated")
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        Formatted string containing image search results with titles and URLs
    """
    try:
        api_key = get_google_custom_search_api_key()
        cse_id = get_google_cse_id()

        logger.info(f"🖼️ Searching images for: {query}")

        # Build the Google Custom Search API service
        service = build("customsearch", "v1", developerKey=api_key)

        # Prepare search parameters for image search
        search_params = {
            "q": query,
            "cx": cse_id,
            "num": min(num_results, 10),
            "safe": safe_search,
            "searchType": "image",
        }

        # Add optional image filters
        if image_size:
            search_params["imgSize"] = image_size
        if image_type:
            search_params["imgType"] = image_type

        # Execute the search
        result = service.cse().list(**search_params).execute()

        # Check if we got results
        if "items" not in result:
            logger.info(f"No image results found for '{query}'")
            return f"No image results found for '{query}'. Try a different search term."

        # Format the results
        formatted_results = []
        formatted_results.append(f"Image search results for '{query}':\n")

        for i, item in enumerate(result["items"], 1):
            title = item.get("title", "No title")
            link = item.get("link", "")
            display_link = item.get("displayLink", "")

            formatted_results.append(f"{i}. **{title}**")
            formatted_results.append(f"   Image URL: {link}")
            formatted_results.append(f"   From: {display_link}")
            formatted_results.append("")  # Empty line for spacing

        # Add search metadata
        search_info = result.get("searchInformation", {})
        total_results = search_info.get("totalResults", "unknown")

        formatted_results.append(f"Found {total_results} total image results")

        result_text = "\n".join(formatted_results)
        logger.info(f"✅ Image search completed: {len(result['items'])} results")

        return result_text

    except HttpError as e:
        error_msg = f"Google API error: {e.status_code} - {e.error_details}"
        logger.error(f"❌ Image search failed: {error_msg}")
        return f"Image search failed due to API error: {error_msg}"

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return f"Image search unavailable: {str(e)}"

    except Exception as e:
        logger.error(f"❌ Unexpected error during image search: {e}")
        return f"Image search failed due to unexpected error: {str(e)}"


@registered_tool()
@rate_limited(resource="google-search", max_requests=100, period="day")
async def search_images(
    query: str,
    num_results: int = 3,
    image_size: Optional[str] = None,
    image_type: Optional[str] = None,
    safe_search: str = "active",
) -> str:
    """
    Search for images using Google Custom Search API.

    Use this tool when you need to find images related to a topic.

    Args:
        query: Image search query string
        num_results: Number of image results to return (1-10, default 3)
        image_size: Image size filter ("small", "medium", "large", "xlarge", "xxlarge", "huge")
        image_type: Image type filter ("clipart", "face", "lineart", "stock", "photo", "animated")
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        Formatted string containing image search results with titles and URLs
    """
    return await _search_images_impl(
        query, num_results, image_size, image_type, safe_search
    )
