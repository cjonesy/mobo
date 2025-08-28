"""
OpenAI-powered tools for AI-generated content.

This module contains tools that use OpenAI services like DALL-E for image generation,
and potentially other OpenAI services in the future.
"""

import logging
from typing import Tuple, Dict
from openai import AsyncOpenAI
from ..config import get_settings
from .common import registered_tool

logger = logging.getLogger(__name__)


def get_openai_client() -> AsyncOpenAI:
    """Get configured OpenAI client."""
    settings = get_settings()

    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")

    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url="https://api.openai.com/v1",
    )


@registered_tool(response_format="content_and_artifact")
async def generate_image(prompt: str) -> Tuple[str, Dict]:
    """
    Generate an image using DALL-E based on a text prompt.

    Args:
        prompt: Description of the image to generate

    Returns:
        Tuple of (content_text, image_artifact)
    """
    try:
        client = get_openai_client()

        logger.info(f"🎨 Generating image with prompt: {prompt[:50]}...")

        response = await client.images.generate(prompt=prompt, n=1, size="1024x1024")

        image_url = response.data[0].url
        logger.info(f"✅ Image generated successfully: {image_url}")

        # Return content for LLM + structured artifact for Discord handler
        content = "I've generated an image for you!"
        artifact = {
            "type": "image",
            "url": image_url,
            "should_upload": True,
            "extension": ".png",
            "filename": f"{response.created}.png",
        }

        return content, artifact

    except Exception as e:
        logger.error(f"❌ Image generation failed for prompt '{prompt[:50]}...': {e}")
        return "", {}
