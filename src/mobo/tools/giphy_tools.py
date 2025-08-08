"""Tools for interacting with the Giphy API."""

from typing import Optional, TypedDict, List
from urllib.parse import urlencode

import httpx
from langchain.tools import BaseTool
from pydantic import Field

from ..config import get_config


class GiphyImage(TypedDict):
    """Type for Giphy image data."""

    url: str
    width: str
    height: str


class GiphyImages(TypedDict):
    """Type for Giphy image renditions."""

    original: GiphyImage
    fixed_height: GiphyImage
    fixed_width: GiphyImage
    downsized: GiphyImage


class GiphyGif(TypedDict):
    """Type for Giphy GIF data."""

    type: str
    id: str
    url: str
    title: str
    images: GiphyImages


class GiphyResponse(TypedDict):
    """Type for Giphy API response."""

    data: List[GiphyGif]
    meta: dict
    pagination: dict


class SearchGiphyTool(BaseTool):
    """Tool for searching Giphy and getting a GIF URL."""

    name: str = Field(default="search_giphy")
    description: str = Field(
        default="""
    Search Giphy for GIFs matching a query and return a URL.
    Use this when you want to find and share a relevant GIF.

    Input should be a search query string.
    Output will be a URL to a relevant GIF.
    """
    )

    class Config:
        arbitrary_types_allowed = True

    # Tool-specific fields
    base_url: str = "https://api.giphy.com/v1"
    api_key: str = Field(
        default_factory=lambda: get_config().giphy_api_key.get_secret_value()
    )
    client: httpx.Client = Field(default_factory=lambda: httpx.Client(timeout=10.0))

    def _build_url(self, endpoint: str, params: dict) -> str:
        """Build a Giphy API URL with parameters."""
        params["api_key"] = self.api_key
        query = urlencode(params)
        return f"{self.base_url}/{endpoint}?{query}"

    def _search(
        self, query: str, rating: str = "g", limit: int = 1
    ) -> Optional[GiphyResponse]:
        """Perform a Giphy search."""
        params = {
            "q": query,
            "limit": limit,
            "rating": rating,
            "lang": "en",
            "bundle": "messaging_non_clips",  # Get optimal renditions for messaging
        }

        url = self._build_url("gifs/search", params)

        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Error calling Giphy API: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error searching Giphy: {e}")

    def _run(self, query: str) -> Optional[str]:
        """Run the Giphy search."""
        response = self._search(query)

        if not response or not response["data"]:
            return None

        gif = response["data"][0]

        return gif["images"]["original"]["url"]

    async def _arun(self, query: str) -> Optional[str]:
        """Async implementation."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {
                "q": query,
                "limit": 1,
                "rating": "g",
                "lang": "en",
                "bundle": "messaging_non_clips",
            }

            url = self._build_url("gifs/search", params)

            try:
                response = await client.get(url)
                response.raise_for_status()
                result = response.json()

                if not result or not result["data"]:
                    return None

                gif = result["data"][0]

                return gif["images"]["original"]["url"]

            except httpx.HTTPError as e:
                raise RuntimeError(f"Error calling Giphy API: {e}")
            except Exception as e:
                raise RuntimeError(f"Unexpected error searching Giphy: {e}")
