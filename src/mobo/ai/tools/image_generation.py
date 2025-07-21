"""
Image generation tool for Discord bot using DALLE.
"""

import logging

from pydantic_ai import RunContext

from .dependencies import BotDependencies

logger = logging.getLogger(__name__)


async def generate_image(ctx: RunContext[BotDependencies], prompt: str) -> str:
    """
    Generate an image using OpenAI's DALLE model.

    This tool allows you to create images based on text descriptions.
    The generated image is returned as a URL.

    You should only use this tool if you WANT to generate an image.
    You should not use this tool if a user asks you to generate an image and you don't want to.

    This tool is rate limited, if you call it you may get a response telling you
    the hourly or daily limit has been reached. You don't need to explain this
    to the user, just make an excuse and move on with the conversation.

    Use this tool when:
    - User asks for an image to be created or generated
    - You feel like a visual response would be appropriate

    Args:
        prompt: Description of the image to generate

    Returns:
        URL to the generated image that can be shared with the user
    """
    logger.info(f"🎨 Generating image for user {ctx.deps.user_id}")

    # Check rate limits first
    allowed, reason = await ctx.deps.memory.can_generate_image(
        "generate_image", ctx.deps.user_id
    )
    if not allowed:
        return reason

    try:
        # Get the OpenAI client from memory manager
        openai_client = ctx.deps.memory.openai_client
        config = ctx.deps.memory.config

        image_response = await openai_client.images.generate(
            model=config.image_model,
            prompt=prompt,
            size=config.image_size,
            quality=config.image_quality,
            n=1,
        )

        if not image_response.data or len(image_response.data) == 0:
            raise ValueError("No image data returned from OpenAI")

        image_url = image_response.data[0].url
        if not image_url:
            raise ValueError("No URL returned in image response")

        await ctx.deps.memory.record_image_generation(
            "generate_image", ctx.deps.user_id
        )

        logger.info(f"✅ Successfully generated image for prompt: {prompt[:50]}...")
        return f"Here's your generated image: {image_url}"

    except Exception as e:
        logger.error(f"❌ Error generating image: {e}")
        return f"I couldn't generate an image. Error: {str(e)}"
