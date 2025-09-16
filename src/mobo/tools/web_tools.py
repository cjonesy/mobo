"""
Web tools including search and URL content processing.

This module contains tools that use the Google Custom Search API to search
the web and return relevant results, as well as tools for fetching and
summarizing web content.
"""

import json
import logging
import aiohttp
import html2text
from textwrap import dedent
from typing import Optional
from urllib.parse import urlparse
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from langchain_openai import ChatOpenAI

from ..config import settings
from .common import tool
from .schemas import UrlSummaryResponse
from ..utils.rate_limiting import rate_limited

logger = logging.getLogger(__name__)


async def _google_search_impl(
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
        logger.info(f"🔍 Searching web for: {query}")

        # Build the Google Custom Search API service
        service = build(
            "customsearch",
            "v1",
            developerKey=settings.google_search.api_key.get_secret_value(),
        )

        # Prepare search parameters
        search_params = {
            "q": query,
            "cx": settings.google_search.cse_id,
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
        result = await _google_search_impl(query, num_results, search_type, safe_search)
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


@tool
@rate_limited(resource="google-search", max_requests=100, period="day")
async def search_images(
    query: str, num_results: int = 3, safe_search: str = "active"
) -> str:
    """
    Searches for images using Google Custom Search API.

    Finds images related to topics through Google's image search infrastructure.

    Examples: Finding reference images, looking up visual examples, getting photos
    for context, finding diagrams or illustrations, discovering visual content.

    Args:
        query: Image search query string
        num_results: Number of image results to return (1-10, default 3)
        safe_search: Safe search setting ("active", "moderate", "off")

    Returns:
        JSON string with search results (same structure as search_web)
    """
    return await _google_search_impl(query, num_results, "image", safe_search)


@tool
async def fetch_and_summarize_url(url: str) -> UrlSummaryResponse:
    """Fetches content from a URL and provides an AI-generated summary.

    Downloads web page content and uses an LLM to generate an intelligent summary
    of the text content, extracting key information and context.

    Examples: Understanding shared links, analyzing news articles, getting content
    overviews, extracting key points from web pages, summarizing documentation.

    Args:
        url: The URL to fetch and summarize

    Returns:
        Structured response containing URL info, title, and AI-generated summary
    """
    logger.info(f"🌐 Calling fetch_and_summarize_url", extra={"url": url})

    try:
        # Parse URL to get domain info
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        # Fetch the webpage content
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return UrlSummaryResponse(
                        success=False,
                        error=f"Failed to fetch URL: HTTP {response.status}",
                        url=url,
                        domain=domain,
                    )

                content = await response.text()

        logger.info(f"📄 Fetched content ({len(content)} characters)")

        # Extract clean text from HTML using html2text
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0  # Don't wrap lines
        text_content = h.handle(content).strip()

        # Limit text content based on configuration
        if len(text_content) > settings.summarization_llm.max_chars:
            text_content = text_content[: settings.summarization_llm.max_chars] + "..."

        logger.info(f"📝 Extracted text content ({len(text_content)} characters)")

        # Use ChatOpenAI with OpenRouter to summarize the content

        llm = ChatOpenAI(
            api_key=settings.openrouter.api_key.get_secret_value(),
            base_url=settings.openrouter.base_url,
            model=settings.summarization_llm.model,
            temperature=settings.summarization_llm.temperature,
        )

        # Create summarization prompt
        prompt = dedent(
            f"""
            Please analyze this web page content and provide:
            1. A clear, concise title if one isn't obvious
            2. A 2-3 sentence summary of the main content
            3. The type of content (article, product page, documentation, etc.)

            Web content:
            {text_content}

            Respond in this format:
            Title: [extracted or inferred title]
            Content Type: [type of content]
            Summary: [2-3 sentence summary]
        """
        ).strip()

        response = await llm.ainvoke(prompt)
        summary_text = response.content

        # Parse the response to extract components
        lines = summary_text.split("\n")
        title = "Unknown Title"
        content_type = "webpage"
        summary = summary_text

        for line in lines:
            if line.startswith("Title:"):
                title = line[6:].strip()
            elif line.startswith("Content Type:"):
                content_type = line[13:].strip()
            elif line.startswith("Summary:"):
                summary = line[8:].strip()

        logger.info(f"✅ URL summarized successfully: {title}")

        return UrlSummaryResponse(
            success=True,
            url=url,
            title=title,
            summary=summary,
            content_type=content_type,
            domain=domain,
        )

    except aiohttp.ClientError as e:
        logger.error(f"❌ Network error fetching URL: {e}")
        return UrlSummaryResponse(
            success=False,
            error=f"Network error: {str(e)}",
            url=url,
            domain=parsed_url.netloc if "parsed_url" in locals() else None,
        )

    except Exception as e:
        logger.error(f"❌ Failed to fetch and summarize URL: {e}")
        return UrlSummaryResponse(
            success=False,
            error=str(e),
            url=url,
            domain=parsed_url.netloc if "parsed_url" in locals() else None,
        )
