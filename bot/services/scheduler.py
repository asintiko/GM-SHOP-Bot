"""
Scheduler service - manages periodic tasks using APScheduler.
"""

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog
import pytz

from bot.config import settings
from bot.database.connection import db
from bot.database import models
from bot.services.weekly_top import weekly_top_service

logger = structlog.get_logger(__name__)


class SchedulerService:
    """Service for managing scheduled tasks."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(settings.tz))
        self.bot = None

    def set_bot(self, bot):
        """Set bot instance for scheduled tasks."""
        self.bot = bot

    async def start(self):
        """Start the scheduler."""
        # Add weekly competition start notification (Monday 00:00)
        self.scheduler.add_job(
            self.notify_weekly_start,
            trigger=CronTrigger(
                day_of_week=0,  # Monday
                hour=0,
                minute=0,
                timezone=settings.tz
            ),
            id='weekly_start',
            name='Notify weekly competition start',
            replace_existing=True
        )

        # Add weekly competition end notification (Monday 11:55)
        self.scheduler.add_job(
            self.notify_weekly_end,
            trigger=CronTrigger(
                day_of_week=0,  # Monday
                hour=11,
                minute=55,
                timezone=settings.tz
            ),
            id='weekly_end',
            name='Notify weekly competition end',
            replace_existing=True
        )

        # Add weekly top task (Monday 12:00)
        self.scheduler.add_job(
            self.publish_weekly_tops,
            trigger=CronTrigger(
                day_of_week=0,  # Monday
                hour=12,
                minute=0,
                timezone=settings.tz
            ),
            id='weekly_top',
            name='Publish weekly tops',
            replace_existing=True
        )

        # Add cleanup task (daily at 3 AM)
        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger=CronTrigger(
                hour=3,
                minute=0,
                timezone=settings.tz
            ),
            id='cleanup',
            name='Cleanup old data',
            replace_existing=True
        )

        # Add expired sanctions check (every hour)
        self.scheduler.add_job(
            self.check_expired_sanctions,
            trigger='interval',
            hours=1,
            id='expired_sanctions',
            name='Check expired sanctions',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("scheduler_started", jobs=len(self.scheduler.get_jobs()))

    async def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("scheduler_stopped")

    async def notify_weekly_start(self):
        """Send weekly competition start notifications to all chats."""
        if not self.bot:
            logger.error("bot_not_set_for_scheduler")
            return

        logger.info("notifying_weekly_start")

        # Get all chats
        chats = await db.fetch("SELECT chat_id, settings FROM chats")

        for chat in chats:
            chat_id = chat['chat_id']
            settings_dict = chat['settings']

            try:
                # Check if notifications are enabled
                weekly_settings = settings_dict.get("weekly_top", {})
                if not weekly_settings.get("enabled", True):
                    continue

                if not weekly_settings.get("notify_start", True):
                    continue

                # Get start message
                start_message = weekly_settings.get(
                    "start_message",
                    "🏁 <b>Новый конкурс топа недели начался!</b>\n\nУчаствуйте в жизни чата, набирайте карму и выигрывайте призы! 🎁"
                )

                await self.bot.send_message(chat_id, start_message)
                logger.info("weekly_start_notified", chat_id=chat_id)

            except Exception as e:
                logger.error(
                    "failed_to_notify_weekly_start",
                    chat_id=chat_id,
                    error=str(e)
                )

    async def notify_weekly_end(self):
        """Send weekly competition end notifications to all chats."""
        if not self.bot:
            logger.error("bot_not_set_for_scheduler")
            return

        logger.info("notifying_weekly_end")

        # Get all chats
        chats = await db.fetch("SELECT chat_id, settings FROM chats")

        for chat in chats:
            chat_id = chat['chat_id']
            settings_dict = chat['settings']

            try:
                # Check if notifications are enabled
                weekly_settings = settings_dict.get("weekly_top", {})
                if not weekly_settings.get("enabled", True):
                    continue

                if not weekly_settings.get("notify_end", True):
                    continue

                # Get end message
                end_message = weekly_settings.get(
                    "end_message",
                    "🏆 <b>Конкурс топа недели завершен!</b>\n\nПобедители будут объявлены в ближайшее время!"
                )

                await self.bot.send_message(chat_id, end_message)
                logger.info("weekly_end_notified", chat_id=chat_id)

            except Exception as e:
                logger.error(
                    "failed_to_notify_weekly_end",
                    chat_id=chat_id,
                    error=str(e)
                )

    async def publish_weekly_tops(self):
        """Publish weekly tops for all chats."""
        if not self.bot:
            logger.error("bot_not_set_for_scheduler")
            return

        logger.info("publishing_weekly_tops")

        # Get all chats
        chats = await db.fetch("SELECT chat_id, settings FROM chats")

        for chat in chats:
            chat_id = chat['chat_id']
            settings_dict = chat['settings']

            try:
                # Check if weekly top is enabled
                weekly_settings = settings_dict.get("weekly_top", {})
                if not weekly_settings.get("enabled", True):
                    continue

                # Publish top
                await weekly_top_service.publish_top(
                    chat_id,
                    settings_dict,
                    self.bot
                )

                logger.info("weekly_top_published", chat_id=chat_id)

            except Exception as e:
                logger.error(
                    "failed_to_publish_weekly_top",
                    chat_id=chat_id,
                    error=str(e)
                )

    async def cleanup_old_data(self):
        """Clean up old data from database."""
        logger.info("cleaning_up_old_data")

        try:
            # Clean up old message logs (older than 7 days)
            await models.cleanup_old_message_logs(days=7)

            # Clean up old audit logs (older than 90 days)
            await db.execute(
                "DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL '90 days'"
            )

            logger.info("cleanup_completed")

        except Exception as e:
            logger.error("cleanup_failed", error=str(e))

    async def check_expired_sanctions(self):
        """Check and deactivate expired sanctions."""
        try:
            # Deactivate expired sanctions
            result = await db.execute(
                """
                UPDATE sanctions
                SET is_active = FALSE
                WHERE is_active = TRUE
                AND expires_at IS NOT NULL
                AND expires_at < NOW()
                """
            )

            if result != "UPDATE 0":
                logger.info("expired_sanctions_deactivated", result=result)

        except Exception as e:
            logger.error("failed_to_check_expired_sanctions", error=str(e))


# Global instance
scheduler_service = SchedulerService()
