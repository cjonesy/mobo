"""
Embedding generation utilities for RAG functionality.

This module provides functions to generate OpenAI embeddings for text content,
used for semantic similarity search in conversation history.
"""

import logging
from typing import List

from openai import AsyncOpenAI
from ..config import settings

logger = logging.getLogger(__name__)


async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI's text-embedding model.

    Args:
        text: Text content to embed

    Returns:
        List of float values representing the text embedding

    Raises:
        Exception: If embedding generation fails
    """
    if not text or text.strip() == "":
        logger.warning("🗂️ Empty text provided for embedding generation")
        # Return zero vector for empty text
        return [0.0] * 1536  # text-embedding-3-small dimension

    try:
        client = AsyncOpenAI(
            api_key=settings.openai.api_key.get_secret_value(),
            base_url=settings.openai.base_url,
        )

        # Clean and truncate text if too long
        clean_text = text.strip()
        if len(clean_text) > 8000:  # Safe limit for embedding models
            clean_text = clean_text[:8000]
            logger.info("🗂️ Truncated text to 8000 characters for embedding")

        logger.info(f"🗂️ Generating embedding for text: {clean_text[:100]}...")

        response = await client.embeddings.create(
            model="text-embedding-3-small", input=clean_text
        )

        embedding = response.data[0].embedding
        logger.info(f"✅ Generated embedding with {len(embedding)} dimensions")

        return embedding

    except Exception as e:
        logger.error(f"❌ Failed to generate embedding: {e}")
        raise Exception(f"Embedding generation failed: {str(e)}")


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    if len(a) != len(b):
        raise ValueError("Embeddings must have the same dimension")

    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = sum(x * x for x in a) ** 0.5
    magnitude_b = sum(x * x for x in b) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single API call.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors corresponding to input texts
    """
    if not texts:
        return []

    try:
        client = AsyncOpenAI(
            api_key=settings.openai.api_key.get_secret_value(),
            base_url=settings.openai.base_url,
        )

        # Clean and truncate texts
        clean_texts = []
        for text in texts:
            clean_text = text.strip() if text else ""
            if len(clean_text) > 8000:
                clean_text = clean_text[:8000]
            clean_texts.append(clean_text)

        logger.info(f"🗂️ Generating embeddings for {len(clean_texts)} texts")

        response = await client.embeddings.create(
            model="text-embedding-3-small", input=clean_texts
        )

        embeddings = [data.embedding for data in response.data]
        logger.info(f"✅ Generated {len(embeddings)} embeddings")

        return embeddings

    except Exception as e:
        logger.error(f"❌ Failed to generate batch embeddings: {e}")
        raise Exception(f"Batch embedding generation failed: {str(e)}")
