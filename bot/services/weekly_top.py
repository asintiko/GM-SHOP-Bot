"""
Weekly top service - calculates and publishes weekly top users.
"""

from datetime import datetime, timedelta
from typing import List, Dict
import structlog

from bot.database.connection import db
from bot.database import models

logger = structlog.get_logger(__name__)


class WeeklyTopService:
    """Service for managing weekly top users."""

    async def calculate_top(
        self,
        chat_id: int,
        settings: dict,
        limit: int = 3
    ) -> List[Dict]:
        """
        Calculate top users for the week.

        Args:
            chat_id: Chat ID
            settings: Chat settings
            limit: Number of top users to return

        Returns:
            List of top users with scores
        """
        top_settings = settings.get("weekly_top", {})
        formula = top_settings.get("formula", {})

        # Get weights from formula
        messages_weight = formula.get("messages_weight", 1)
        karma_weight = formula.get("karma_weight", 2)
        replies_weight = formula.get("replies_weight", 0.5)
        reactions_weight = formula.get("reactions_weight", 0.3)

        # Get exclusion threshold
        exclude_muted_hours = top_settings.get("exclude_if_muted_hours", 24)

        # Calculate scores using SQL
        query = f"""
            WITH user_scores AS (
                SELECT
                    cm.user_id,
                    u.first_name,
                    u.username,
                    cm.messages_week,
                    cm.karma,
                    cm.replies_received_week,
                    cm.reactions_received_week,
                    (
                        cm.messages_week * {messages_weight} +
                        cm.karma * {karma_weight} +
                        cm.replies_received_week * {replies_weight} +
                        cm.reactions_received_week * {reactions_weight}
                    ) as score,
                    -- Check if user was muted for long duration
                    (
                        SELECT COALESCE(SUM(duration_seconds), 0)
                        FROM sanctions
                        WHERE chat_id = $1
                        AND target_user_id = cm.user_id
                        AND type = 'mute'
                        AND is_active = TRUE
                        AND created_at >= NOW() - INTERVAL '7 days'
                    ) as total_mute_seconds
                FROM chat_members cm
                JOIN users u ON cm.user_id = u.user_id
                WHERE cm.chat_id = $1
                AND cm.messages_week > 0
            )
            SELECT
                user_id,
                first_name,
                username,
                messages_week,
                karma,
                score
            FROM user_scores
            WHERE total_mute_seconds < {exclude_muted_hours * 3600}
            ORDER BY score DESC
            LIMIT $2
        """

        results = await db.fetch(query, chat_id, limit)

        top_users = []
        for idx, row in enumerate(results, 1):
            top_users.append({
                'rank': idx,
                'user_id': row['user_id'],
                'first_name': row['first_name'],
                'username': row['username'],
                'messages': row['messages_week'],
                'karma': row['karma'],
                'score': round(float(row['score']), 2)
            })

        return top_users

    async def publish_top(
        self,
        chat_id: int,
        settings: dict,
        bot
    ) -> bool:
        """
        Calculate and publish weekly top to chat.

        Args:
            chat_id: Chat ID
            settings: Chat settings
            bot: Bot instance

        Returns:
            True if published successfully
        """
        top_settings = settings.get("weekly_top", {})

        if not top_settings.get("enabled", True):
            return False

        # Calculate top
        top_count = top_settings.get("top_count", 3)
        top_users = await self.calculate_top(chat_id, settings, top_count)

        if not top_users:
            logger.warning("no_users_for_top", chat_id=chat_id)
            return False

        # Get prizes
        prizes = top_settings.get("prizes", [
            "🥇 Донат на 500 руб",
            "🥈 Донат на 300 руб",
            "🥉 Донат на 200 руб"
        ])

        # Build message
        message_text = "<b>ТОП недели в «GM SHOP» 🎉</b>\n\n"

        medals = ["🥇", "🥈", "🥉"]
        for user in top_users:
            rank = user['rank']
            medal = medals[rank - 1] if rank <= 3 else f"{rank}."
            message_text += (
                f'{medal} <a href="tg://user?id={user["user_id"]}">{user["first_name"]}</a> '
                f'— {user["score"]} очков\n'
            )

        message_text += "\n🎁 Призы недели:\n"
        for idx, prize in enumerate(prizes[:len(top_users)], 1):
            message_text += f"{idx}) {prize}\n"

        message_text += "\n<i>Стань активнее: полезные сообщения, помощь другим и уважительное общение!</i>"

        # Send message
        try:
            await bot.send_message(chat_id, message_text)
            logger.info("weekly_top_published", chat_id=chat_id, users_count=len(top_users))

            # Save to database
            await self._save_top_result(chat_id, top_users)

            # Reset weekly stats
            await models.reset_weekly_stats(chat_id)

            return True

        except Exception as e:
            logger.error("failed_to_publish_top", chat_id=chat_id, error=str(e))
            return False

    async def _save_top_result(self, chat_id: int, top_users: List[Dict]):
        """Save weekly top result to database."""
        week_end = datetime.now()
        week_start = week_end - timedelta(days=7)

        import json
        await db.execute(
            """
            INSERT INTO weekly_tops (chat_id, week_start, week_end, results)
            VALUES ($1, $2, $3, $4)
            """,
            chat_id, week_start, week_end, json.dumps(top_users)
        )


# Global instance
weekly_top_service = WeeklyTopService()
