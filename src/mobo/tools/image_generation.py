"""Image generation tool using DALL-E."""

import logging
from typing import Any

from langchain_core.tools import tool

from ..config import get_config

logger = logging.getLogger(__name__)


@tool
async def generate_image(prompt: str) -> Any:
    """Generate an image using DALL-E based on a text prompt.

    Use this tool when you want to create an image for the conversation.

    IMPORTANT INSTRUCTIONS:
    1. The image will be automatically attached to your response
    2. NEVER include the image URL in your response text
    3. NEVER mention that you're attaching an image - just describe what you created
    4. BAD: "Here's the image I generated: [URL]" or "I've attached an image of..."
    5. GOOD: "I drew a happy dog playing in the park." or "The emoji shows a smiling face"

    Args:
        prompt: Description of the image to generate

    Returns:
        Dictionary containing response data for structured processing on success,
        or error message string on failure
    """
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        config = get_config()

        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=config.openrouter_api_key.get_secret_value(),
            base_url=config.openrouter_base_url,
        )

        logger.info(f"Generating image with prompt: {prompt}")

        response = await client.images.generate(
            model=config.image_model,
            prompt=prompt,
            size=config.image_size,
            quality=config.image_quality,
            n=1,
        )

        if response.data and response.data[0].url:
            image_url = response.data[0].url
            logger.info(f"Generated image: {image_url}")

            return {"url": image_url}
        else:
            return "ERROR: Image generation failed. No image was created."

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return f"ERROR: Image generation failed with exception: {str(e)}"
