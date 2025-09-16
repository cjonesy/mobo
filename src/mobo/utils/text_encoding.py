"""
Text encoding utilities for configuration and content processing.

This module provides utilities for handling different text encodings,
particularly base64 decoding for configuration values.
"""

import base64
import logging

logger = logging.getLogger(__name__)


def decode_base64_if_encoded(text: str) -> str:
    """
    Attempt to decode text as base64, falling back to original if not encoded.

    This is useful for configuration values that might be base64 encoded
    for security or storage reasons.

    Args:
        text: Text that might be base64 encoded

    Returns:
        Decoded text if it was valid base64, otherwise the original text
    """
    if not text:
        return text

    try:
        # Attempt to decode as base64
        decoded_bytes = base64.b64decode(text)
        decoded_text = decoded_bytes.decode("utf-8")

        logger.info(f"Successfully decoded base64 text ({len(decoded_text)} chars)")
        return decoded_text

    except Exception as e:
        logger.debug(f"Text is not base64 encoded: {e}")
        # Return original text if decoding fails
        return text


def is_likely_base64(text: str) -> bool:
    """
    Check if text is likely to be base64 encoded.

    This is a heuristic check - not foolproof but catches common cases.

    Args:
        text: Text to check

    Returns:
        True if text appears to be base64 encoded
    """
    if not text:
        return False

    # Basic checks for base64 characteristics
    if len(text) % 4 != 0:
        return False

    # Check for base64 character set
    import string

    base64_chars = string.ascii_letters + string.digits + "+/="
    return all(c in base64_chars for c in text)


def encode_text_as_base64(text: str) -> str:
    """
    Encode text as base64.

    Args:
        text: Text to encode

    Returns:
        Base64 encoded text
    """
    if not text:
        return text

    encoded_bytes = base64.b64encode(text.encode("utf-8"))
    return encoded_bytes.decode("ascii")
