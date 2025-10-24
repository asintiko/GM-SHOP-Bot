"""
Antiflood service - detects and handles message flooding.
Implements "6 messages in a row" detection from specification.
"""

from datetime import datetime, timedelta
from typing import Optional
import structlog

from bot.database import models
from bot.database.connection import db

logger = structlog.get_logger(__name__)


class AntifloodService:
    """Service for detecting and handling message flooding."""

    def __init__(self):
        # Cache for recent messages per chat
        # Structure: {chat_id: [(user_id, message_id, timestamp), ...]}
        self._message_cache = {}
        self._cache_size = 50  # Keep last 50 messages per chat

    async def check_flood(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        settings: dict
    ) -> tuple[bool, int]:
        """
        Check if user is flooding the chat.

        Args:
            chat_id: Chat ID
            user_id: User ID
            message_id: Message ID
            settings: Chat settings (antiflood config)

        Returns:
            Tuple of (is_flooding, consecutive_count)
        """
        antiflood_settings = settings.get("antiflood", {})

        # Check if antiflood is enabled
        if not antiflood_settings.get("enabled", True):
            return False, 0

        # Get settings
        threshold = antiflood_settings.get("messages_count", 6)
        window_minutes = antiflood_settings.get("window_minutes", 3)

        # Log message
        await models.log_message(chat_id, user_id, message_id)

        # Get recent messages from this user
        recent_messages = await models.get_recent_messages(
            chat_id, user_id, window_minutes
        )

        # Count consecutive messages
        consecutive_count = await self._count_consecutive_messages(
            chat_id, user_id, window_minutes
        )

        logger.debug(
            "antiflood_check",
            chat_id=chat_id,
            user_id=user_id,
            consecutive=consecutive_count,
            threshold=threshold
        )

        # Check if threshold exceeded
        if consecutive_count >= threshold:
            logger.warning(
                "flood_detected",
                chat_id=chat_id,
                user_id=user_id,
                count=consecutive_count
            )
            return True, consecutive_count

        return False, consecutive_count

    async def _count_consecutive_messages(
        self,
        chat_id: int,
        user_id: int,
        window_minutes: int
    ) -> int:
        """
        Count consecutive messages from user without interruption.

        Args:
            chat_id: Chat ID
            user_id: User ID
            window_minutes: Time window in minutes

        Returns:
            Number of consecutive messages
        """
        # Get recent messages from all users in chat
        since = datetime.now() - timedelta(minutes=window_minutes)

        # Query to get last N messages in order
        messages = await db.fetch(
            """
            SELECT user_id, message_id, created_at
            FROM message_log
            WHERE chat_id = $1 AND created_at > $2
            ORDER BY created_at DESC
            LIMIT 50
            """,
            chat_id, since
        )

        if not messages:
            return 0

        # Count consecutive from the beginning (newest messages)
        consecutive = 0
        for msg in messages:
            if msg['user_id'] == user_id:
                consecutive += 1
            else:
                # Different user interrupted the sequence
                break

        return consecutive

    async def get_mute_duration(self, settings: dict) -> int:
        """
        Get mute duration in seconds from settings.

        Args:
            settings: Chat settings

        Returns:
            Mute duration in seconds
        """
        antiflood_settings = settings.get("antiflood", {})
        minutes = antiflood_settings.get("mute_duration_minutes", 50)
        return minutes * 60

    async def should_delete_messages(self, settings: dict) -> bool:
        """
        Check if flood messages should be deleted.

        Args:
            settings: Chat settings

        Returns:
            True if messages should be deleted
        """
        antiflood_settings = settings.get("antiflood", {})
        return antiflood_settings.get("delete_messages", True)


# Global instance
antiflood_service = AntifloodService()
