"""
Karma service - handles karma system for users.
Implements positive/negative karma with cooldowns and limits.
"""

from datetime import datetime, timedelta
import structlog

from bot.database import models
from bot.database.connection import db
from bot.utils.filters import content_filter

logger = structlog.get_logger(__name__)


class KarmaService:
    """Service for managing user karma."""

    async def process_message_for_karma(
        self,
        chat_id: int,
        from_user_id: int,
        to_user_id: int,
        text: str,
        settings: dict
    ) -> tuple[bool, int, str]:
        """
        Process message for karma changes.

        Args:
            chat_id: Chat ID
            from_user_id: User giving karma
            to_user_id: User receiving karma
            text: Message text
            settings: Chat settings

        Returns:
            Tuple of (karma_changed, delta, reason)
        """
        karma_settings = settings.get("karma", {})

        # Check if karma is enabled
        if not karma_settings.get("enabled", True):
            return False, 0, ""

        # Check if users are different (can't give karma to yourself)
        if from_user_id == to_user_id:
            return False, 0, "self_karma"

        # Check for positive karma triggers
        if content_filter.check_positive_karma(text):
            return await self._add_positive_karma(
                chat_id, from_user_id, to_user_id, text, karma_settings
            )

        # Check for negative karma triggers
        if content_filter.check_negative_karma(text):
            return await self._add_negative_karma(
                chat_id, from_user_id, to_user_id, text, karma_settings
            )

        return False, 0, ""

    async def _add_positive_karma(
        self,
        chat_id: int,
        from_user_id: int,
        to_user_id: int,
        text: str,
        settings: dict
    ) -> tuple[bool, int, str]:
        """Add positive karma (+1)."""

        # Check cooldown
        cooldown_hours = settings.get("cooldown_hours", 12)
        can_give = await models.check_karma_cooldown(
            chat_id, from_user_id, to_user_id, cooldown_hours
        )

        if not can_give:
            logger.debug(
                "karma_cooldown",
                chat_id=chat_id,
                from_user=from_user_id,
                to_user=to_user_id
            )
            return False, 0, "cooldown"

        # Add karma
        await models.add_karma_event(
            chat_id, from_user_id, to_user_id, 1, "positive_trigger"
        )

        logger.info(
            "karma_added",
            chat_id=chat_id,
            from_user=from_user_id,
            to_user=to_user_id,
            delta=1
        )

        return True, 1, "positive"

    async def _add_negative_karma(
        self,
        chat_id: int,
        from_user_id: int,
        to_user_id: int,
        text: str,
        settings: dict
    ) -> tuple[bool, int, str]:
        """Add negative karma (-1) with daily limit."""

        # Check cooldown
        cooldown_hours = settings.get("cooldown_hours", 12)
        can_give = await models.check_karma_cooldown(
            chat_id, from_user_id, to_user_id, cooldown_hours
        )

        if not can_give:
            return False, 0, "cooldown"

        # Check daily negative limit
        daily_limit = settings.get("daily_negative_limit", -3)
        today_negative = await self._get_today_negative_karma(chat_id, to_user_id)

        if today_negative <= daily_limit:
            logger.debug(
                "negative_karma_limit_reached",
                chat_id=chat_id,
                to_user=to_user_id,
                current=today_negative,
                limit=daily_limit
            )
            return False, 0, "daily_limit"

        # Add negative karma
        await models.add_karma_event(
            chat_id, from_user_id, to_user_id, -1, "negative_trigger"
        )

        logger.info(
            "karma_removed",
            chat_id=chat_id,
            from_user=from_user_id,
            to_user=to_user_id,
            delta=-1
        )

        return True, -1, "negative"

    async def _get_today_negative_karma(self, chat_id: int, user_id: int) -> int:
        """Get total negative karma received today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.fetchval(
            """
            SELECT COALESCE(SUM(delta), 0)
            FROM karma_events
            WHERE chat_id = $1 AND to_user_id = $2
            AND created_at >= $3 AND delta < 0
            """,
            chat_id, user_id, today_start
        )

        return result or 0

    async def get_karma_leaderboard(
        self,
        chat_id: int,
        limit: int = 10
    ) -> list[dict]:
        """
        Get karma leaderboard for chat.

        Args:
            chat_id: Chat ID
            limit: Number of top users

        Returns:
            List of users with karma
        """
        results = await db.fetch(
            """
            SELECT cm.user_id, cm.karma, u.first_name, u.username
            FROM chat_members cm
            JOIN users u ON cm.user_id = u.user_id
            WHERE cm.chat_id = $1
            ORDER BY cm.karma DESC
            LIMIT $2
            """,
            chat_id, limit
        )

        return [dict(r) for r in results]


# Global instance
karma_service = KarmaService()
