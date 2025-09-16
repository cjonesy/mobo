"""
Web search tools using Google Custom Search API.

This module contains tools that use the Google Custom Search API to search
the web and return relevant results.
"""

import json
import logging
from typing import Optional
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from ..config import settings
from langchain_core.tools import tool
from .common import register_tool
from ..utils.rate_limiting import rate_limited

logger = logging.getLogger(__name__)


def get_google_custom_search_api_key() -> str:
    """Get Google Custom Search API key."""
    if not settings.google_search.api_key:
        raise ValueError("Google Custom Search API key not configured")

    return settings.google_search.api_key.get_secret_value()


def get_google_cse_id() -> str:
    """Get Google Custom Search Engine ID."""
    if not settings.google_search.cse_id:
        raise ValueError("Google Custom Search Engine ID not configured")

    return settings.google_search.cse_id


async def _search_web_impl(
    query: str,
    num_results: int = 5,
    search_type: Optional[str] = None,
    safe_search: str = "off",
) -> str:
    """
    Internal implementation of web search.

    Args:
        query: Search query string
        num_results: Number of results to return (1-10, default 5)
        search_type: Optional search type ("image" for image search)
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        JSON string containing search results data
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
            return json.dumps(
                {
                    "success": False,
                    "error": f"No search results found for '{query}'. Try a different search term.",
                    "query": query,
                    "results": [],
                }
            )

        # Extract search results
        search_results = []
        for item in result["items"]:
            search_results.append(
                {
                    "title": item.get("title", "No title"),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "No description available"),
                    "display_link": item.get("displayLink", ""),
                }
            )

        # Add search metadata
        search_info = result.get("searchInformation", {})

        logger.info(f"✅ Web search completed: {len(result['items'])} results")

        return json.dumps(
            {
                "success": True,
                "query": query,
                "results": search_results,
                "total_results": search_info.get("totalResults", "unknown"),
                "search_time": search_info.get("searchTime", "unknown"),
                "result_count": len(search_results),
            }
        )

    except HttpError as e:
        error_msg = f"Google API error: {e.status_code} - {e.error_details}"
        logger.error(f"❌ Web search failed: {error_msg}")
        return json.dumps(
            {
                "success": False,
                "error": f"Search failed due to API error: {error_msg}",
                "query": query,
            }
        )

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return json.dumps(
            {"success": False, "error": f"Search unavailable: {str(e)}", "query": query}
        )

    except Exception as e:
        logger.error(f"❌ Unexpected error during web search: {e}")
        return json.dumps(
            {
                "success": False,
                "error": f"Search failed due to unexpected error: {str(e)}",
                "query": query,
            }
        )


@tool
@rate_limited(resource="google-search", max_requests=100, period="day")
async def search_web(
    query: str,
    num_results: int = 5,
    search_type: Optional[str] = None,
    safe_search: str = "active",
) -> str:
    """
    Searches the web using Google Custom Search API and returns structured results.

    Provides access to current information, news, and web content through Google's
    search infrastructure with customizable parameters.

    Examples: Finding recent news, researching topics, getting current information,
    fact-checking, discovering relevant websites, finding specific resources.

    Args:
        query: Search query string
        num_results: Number of results to return (1-10, default 5)
        search_type: Optional search type ("image" for image search)
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        JSON string with structure:
        {
            "success": bool,           # True if search completed successfully
            "query": str,              # The search query that was executed
            "results": [               # Array of search results
                {
                    "title": str,         # Page title
                    "link": str,          # URL to the page
                    "snippet": str,       # Brief description/preview text
                    "display_link": str   # Formatted display URL
                }
            ],
            "total_results": str,      # Total results available (from Google)
            "search_time": str,        # Time taken to perform search
            "result_count": int        # Number of results returned
        }
        On error:
        {
            "success": false,
            "error": str,              # Description of what went wrong
            "query": str               # The search query that failed
        }
    """
    logger.info(
        "⚒️ Calling search_web",
        extra={
            "query": query,
            "num_results": num_results,
            "search_type": search_type,
            "safe_search": safe_search,
        },
    )
    try:
        result = await _search_web_impl(query, num_results, search_type, safe_search)
        logger.info(f"🔍 Web search result length: {len(result)}")
        return result
    except ValueError as e:
        logger.error(f"❌ Web search configuration error: {e}")
        return json.dumps(
            {
                "success": False,
                "error": f"Web search unavailable: {str(e)}. Please configure GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID environment variables.",
                "query": query,
            }
        )
    except Exception as e:
        logger.error(f"❌ Web search error: {e}")
        return json.dumps(
            {"success": False, "error": f"Web search failed: {str(e)}", "query": query}
        )


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
        JSON string containing image search results data
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
            return json.dumps(
                {
                    "success": False,
                    "error": f"No image results found for '{query}'. Try a different search term.",
                    "query": query,
                    "results": [],
                }
            )

        # Extract image results
        image_results = []
        for item in result["items"]:
            image_results.append(
                {
                    "title": item.get("title", "No title"),
                    "link": item.get("link", ""),
                    "display_link": item.get("displayLink", ""),
                    "image": {
                        "context_link": item.get("image", {}).get("contextLink", ""),
                        "height": item.get("image", {}).get("height"),
                        "width": item.get("image", {}).get("width"),
                        "byte_size": item.get("image", {}).get("byteSize"),
                    },
                }
            )

        # Add search metadata
        search_info = result.get("searchInformation", {})

        logger.info(f"✅ Image search completed: {len(result['items'])} results")

        return json.dumps(
            {
                "success": True,
                "query": query,
                "results": image_results,
                "total_results": search_info.get("totalResults", "unknown"),
                "search_time": search_info.get("searchTime", "unknown"),
                "result_count": len(image_results),
                "filters": {
                    "image_size": image_size,
                    "image_type": image_type,
                    "safe_search": safe_search,
                },
            }
        )

    except HttpError as e:
        error_msg = f"Google API error: {e.status_code} - {e.error_details}"
        logger.error(f"❌ Image search failed: {error_msg}")
        return json.dumps(
            {
                "success": False,
                "error": f"Image search failed due to API error: {error_msg}",
                "query": query,
            }
        )

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return json.dumps(
            {
                "success": False,
                "error": f"Image search unavailable: {str(e)}",
                "query": query,
            }
        )

    except Exception as e:
        logger.error(f"❌ Unexpected error during image search: {e}")
        return json.dumps(
            {
                "success": False,
                "error": f"Image search failed due to unexpected error: {str(e)}",
                "query": query,
            }
        )


@tool
@rate_limited(resource="google-search", max_requests=100, period="day")
async def search_images(
    query: str,
    num_results: int = 3,
    image_size: Optional[str] = None,
    image_type: Optional[str] = None,
    safe_search: str = "active",
) -> str:
    """
    Searches for images using Google Custom Search API with filtering options.

    Finds images related to topics with customizable size, type, and safety filters
    through Google's image search infrastructure.

    Examples: Finding reference images, looking up visual examples, getting photos
    for context, finding diagrams or illustrations, discovering visual content.

    Args:
        query: Image search query string
        num_results: Number of image results to return (1-10, default 3)
        image_size: Image size filter ("small", "medium", "large", "xlarge", "xxlarge", "huge")
        image_type: Image type filter ("clipart", "face", "lineart", "stock", "photo", "animated")
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        JSON string with structure:
        {
            "success": bool,           # True if image search completed successfully
            "query": str,              # The search query that was executed
            "results": [               # Array of image results
                {
                    "title": str,         # Image title/description
                    "link": str,          # Direct URL to the image file
                    "display_link": str,  # Domain where image was found
                    "image": {
                        "context_link": str,  # URL of page containing the image
                        "height": int,        # Image height in pixels
                        "width": int,         # Image width in pixels
                        "byte_size": int      # Image file size in bytes
                    }
                }
            ],
            "total_results": str,      # Total results available (from Google)
            "search_time": str,        # Time taken to perform search
            "result_count": int,       # Number of results returned
            "filters": {               # Applied search filters
                "image_size": str,     # Size filter applied (or null)
                "image_type": str,     # Type filter applied (or null)
                "safe_search": str     # Safe search setting used
            }
        }
        On error:
        {
            "success": false,
            "error": str,              # Description of what went wrong
            "query": str               # The search query that failed
        }
    """
    return await _search_images_impl(
        query, num_results, image_size, image_type, safe_search
    )


# Register tools with the global registry
register_tool(search_web)
register_tool(search_images)
