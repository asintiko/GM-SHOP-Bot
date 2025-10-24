"""
GM SHOP Bot - Main entry point
Telegram bot for shop moderation, contests, and community management.
"""

import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import structlog

from bot.config import settings
from bot.database.connection import db

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def on_startup(bot: Bot):
    """Execute actions on bot startup."""
    logger.info("bot_starting", bot_id=(await bot.me()).id)

    # Connect to database
    try:
        await db.connect()
        logger.info("database_connected")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        sys.exit(1)

    # Start scheduler
    from bot.services.scheduler import scheduler_service
    scheduler_service.set_bot(bot)
    await scheduler_service.start()
    logger.info("scheduler_started")

    # Notify owners
    for owner_id in settings.owner_ids:
        try:
            await bot.send_message(
                owner_id,
                "🤖 <b>GM SHOP Bot запущен!</b>\n\n"
                "Бот успешно подключился к базе данных и готов к работе.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning("failed_to_notify_owner", owner_id=owner_id, error=str(e))

    logger.info("bot_started")


async def on_shutdown(bot: Bot):
    """Execute actions on bot shutdown."""
    logger.info("bot_shutting_down")

    # Stop scheduler
    from bot.services.scheduler import scheduler_service
    await scheduler_service.stop()
    logger.info("scheduler_stopped")

    # Notify owners
    for owner_id in settings.owner_ids:
        try:
            await bot.send_message(
                owner_id,
                "🔴 <b>GM SHOP Bot остановлен</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

    # Disconnect from database
    await db.disconnect()
    logger.info("bot_stopped")


async def main():
    """Main function to run the bot."""

    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register middleware
    from bot.middleware.logging_middleware import LoggingMiddleware
    from bot.middleware.admin_check import AdminCheckMiddleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(AdminCheckMiddleware())

    # Register routers (order matters - more specific first)
    from bot.handlers.private.admin_panel import router as admin_panel_router
    from bot.handlers.private.rules_editor import router as rules_editor_router
    from bot.handlers.private.welcome_editor import router as welcome_editor_router
    from bot.handlers.private.giveaway_wizard import router as giveaway_wizard_router
    from bot.handlers.private.karma_manager import router as karma_manager_router
    from bot.handlers.moderation.commands import router as moderation_router
    from bot.handlers.user.commands import router as user_commands_router
    from bot.handlers.user.help import router as help_router
    from bot.handlers.user.statistics import router as statistics_router
    from bot.handlers.user.karma_reactions import router as karma_reactions_router
    from bot.handlers.user.nickname import router as nickname_router
    from bot.handlers.user.welcome import router as welcome_router
    from bot.handlers.user.messages import router as messages_router

    # Private chat handlers (admin panel)
    dp.include_router(admin_panel_router)
    dp.include_router(rules_editor_router)
    dp.include_router(welcome_editor_router)
    dp.include_router(giveaway_wizard_router)
    dp.include_router(karma_manager_router)  # Karma management through PM

    # Group handlers
    dp.include_router(moderation_router)  # Moderation commands
    dp.include_router(user_commands_router)  # User commands (/rules, /karma, etc)
    dp.include_router(help_router)  # Help command
    dp.include_router(statistics_router)  # Statistics commands (!стата, !общстат)
    dp.include_router(karma_reactions_router)  # Karma reactions
    dp.include_router(nickname_router)  # Nickname commands
    dp.include_router(welcome_router)  # Welcome new members
    dp.include_router(messages_router)  # All messages (antiflood, karma, filters) - last!

    logger.info("starting_polling")

    try:
        # Start polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error("polling_error", error=str(e))
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("bot_stopped_by_user")
    except Exception as e:
        logger.error("bot_crashed", error=str(e))
        sys.exit(1)
