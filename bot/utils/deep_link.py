"""
Deep-link utilities for secure chat settings access.
"""

import hmac
import hashlib
from bot.config import settings


def generate_settings_signature(chat_id: int) -> str:
    """
    Generate HMAC signature for settings deep-link.

    Args:
        chat_id: Chat ID to generate signature for

    Returns:
        Hexadecimal signature string
    """
    secret = settings.bot_token  # Use bot token as secret
    message = str(chat_id).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), message, hashlib.sha256)
    return signature.hexdigest()[:16]  # First 16 chars for brevity


def validate_settings_signature(chat_id: int, signature: str) -> bool:
    """
    Validate HMAC signature for settings deep-link.

    Args:
        chat_id: Chat ID to validate
        signature: Signature to validate

    Returns:
        True if signature is valid, False otherwise
    """
    expected = generate_settings_signature(chat_id)
    return hmac.compare_digest(expected, signature)


def create_settings_deep_link(bot_username: str, chat_id: int) -> str:
    """
    Create deep-link URL for chat settings.

    Args:
        bot_username: Bot username (without @)
        chat_id: Chat ID

    Returns:
        Deep-link URL
    """
    signature = generate_settings_signature(chat_id)
    return f"https://t.me/{bot_username}?start=cfg_{chat_id}_{signature}"
