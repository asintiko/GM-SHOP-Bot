"""
Message handler - processes all messages for antiflood, karma, and filters.
"""

from datetime import timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
import structlog

from bot.database import models
from bot.services.antiflood import antiflood_service
from bot.services.karma import karma_service
from bot.utils.filters import content_filter, link_filter

logger = structlog.get_logger(__name__)
router = Router(name="messages")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def process_message(message: Message, bot: Bot):
    """Process all group messages for antiflood, karma, and filters."""

    if not message.from_user or message.from_user.is_bot:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    message_id = message.message_id

    # Get or create user and chat member
    await models.get_or_create_user(
        user_id,
        message.from_user.first_name,
        message.from_user.last_name,
        message.from_user.username,
        message.from_user.is_bot
    )
    await models.get_or_create_chat(chat_id, message.chat.title)
    await models.get_or_create_chat_member(chat_id, user_id)

    # Get chat settings
    settings = await models.get_chat_settings(chat_id)

    # Update message count
    await models.increment_messages_count(chat_id, user_id)

    # Check content filters (earning/casino spam)
    if message.text:
        await check_spam_filters(message, bot, settings)

    # Check antiflood
    await check_antiflood(message, bot, settings)

    # Process karma if this is a reply
    if message.reply_to_message and message.text:
        await process_karma(message, settings)


async def check_spam_filters(message: Message, bot: Bot, settings: dict):
    """Check message for spam patterns."""
    filter_settings = settings.get("filters", {})

    if not filter_settings.get("enabled", True):
        return

    text = message.text

    # Check earning/casino spam
    is_spam, pattern = content_filter.check_earning_spam(text)

    if is_spam:
        logger.warning(
            "spam_detected",
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            pattern=pattern
        )

        # Delete message
        try:
            await message.delete()
        except TelegramBadRequest as e:
            logger.error("failed_to_delete_spam", error=str(e))

        # Apply sanction
        action = filter_settings.get("default_action", "mute_forever")

        if action == "mute_forever":
            # Mute forever
            try:
                await bot.restrict_chat_member(
                    message.chat.id,
                    message.from_user.id,
                    permissions={"can_send_messages": False}
                )

                await models.add_sanction(
                    message.chat.id,
                    message.from_user.id,
                    bot.id,  # Bot as moderator
                    "mute",
                    f"Автомодерация: спам ({pattern[:50]})",
                    None  # Forever
                )

                # Notify in chat
                await message.answer(
                    f'🚫 <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a> '
                    f'получил мут за спам/рекламу.'
                )

            except TelegramBadRequest as e:
                logger.error("failed_to_mute_spammer", error=str(e))

        elif action == "mute_duration":
            # Mute for configured duration
            duration_minutes = filter_settings.get("mute_duration_minutes", 10080)
            duration_seconds = duration_minutes * 60

            try:
                until_date = message.date + timedelta(seconds=duration_seconds)
                await bot.restrict_chat_member(
                    message.chat.id,
                    message.from_user.id,
                    permissions={"can_send_messages": False},
                    until_date=until_date
                )

                await models.add_sanction(
                    message.chat.id,
                    message.from_user.id,
                    bot.id,
                    "mute",
                    f"Автомодерация: спам ({pattern[:50]})",
                    duration_seconds
                )

            except TelegramBadRequest as e:
                logger.error("failed_to_mute_spammer", error=str(e))

    # Check unauthorized links
    if filter_settings.get("check_links", True):
        has_bad_link, link = link_filter.check_unauthorized_link(text)

        if has_bad_link:
            logger.warning(
                "unauthorized_link",
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                link=link
            )

            try:
                await message.delete()
                await message.answer(
                    f'🚫 <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>, '
                    f'ссылки запрещены.'
                )
            except TelegramBadRequest:
                pass


async def check_antiflood(message: Message, bot: Bot, settings: dict):
    """Check for message flooding."""
    is_flooding, count = await antiflood_service.check_flood(
        message.chat.id,
        message.from_user.id,
        message.message_id,
        settings
    )

    if is_flooding:
        # Get mute duration
        duration_seconds = await antiflood_service.get_mute_duration(settings)

        # Mute user
        try:
            until_date = message.date + timedelta(seconds=duration_seconds)
            await bot.restrict_chat_member(
                message.chat.id,
                message.from_user.id,
                permissions={"can_send_messages": False},
                until_date=until_date
            )

            await models.add_sanction(
                message.chat.id,
                message.from_user.id,
                bot.id,
                "mute",
                f"Антифлуд: {count} сообщений подряд",
                duration_seconds
            )

            # Notify
            duration_minutes = duration_seconds // 60
            await message.answer(
                f'🔇 <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a> '
                f'получил мут на <b>{duration_minutes} минут</b> за флуд ({count} сообщений подряд).'
            )

            # Delete flood messages if configured
            if await antiflood_service.should_delete_messages(settings):
                # Get recent messages from this user
                recent_messages = await models.get_recent_messages(
                    message.chat.id,
                    message.from_user.id,
                    3
                )

                for msg in recent_messages[:count]:
                    try:
                        await bot.delete_message(message.chat.id, msg['message_id'])
                    except TelegramBadRequest:
                        pass

        except TelegramBadRequest as e:
            logger.error("failed_to_mute_flooder", error=str(e))


async def process_karma(message: Message, settings: dict):
    """Process message for karma changes."""
    if not message.reply_to_message.from_user:
        return

    from_user_id = message.from_user.id
    to_user_id = message.reply_to_message.from_user.id
    text = message.text

    # Process karma
    changed, delta, reason = await karma_service.process_message_for_karma(
        message.chat.id,
        from_user_id,
        to_user_id,
        text,
        settings
    )

    if changed:
        # Get updated karma
        karma = await models.get_karma(message.chat.id, to_user_id)

        # Notify about karma change
        if delta > 0:
            karma_emoji = "⭐"
            action = "получил"
        else:
            karma_emoji = "💀"
            action = "получил"

        # Don't spam chat with every karma change - only notify sometimes
        # You can make this configurable
        # await message.answer(
        #     f'{karma_emoji} <a href="tg://user?id={to_user_id}">{message.reply_to_message.from_user.first_name}</a> '
        #     f'{action} <b>{delta:+d}</b> к карме! Текущая карма: <b>{karma}</b>'
        # )
