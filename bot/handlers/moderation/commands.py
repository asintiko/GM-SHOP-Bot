"""
Moderation commands handlers (ban, mute, warn, kick, etc.)
"""

from datetime import timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
import structlog

from bot.database import models
from bot.utils.time_parser import parse_time
from bot.utils.deep_link import create_settings_deep_link
from bot.config import settings
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = structlog.get_logger(__name__)
router = Router(name="moderation_commands")


async def is_moderator(chat_id: int, user_id: int) -> bool:
    """Check if user is moderator, admin or owner."""
    if user_id in settings.owner_ids:
        return True
    return await models.is_staff(chat_id, user_id)


async def get_target_user(message: Message) -> tuple[int, str] | None:
    """Extract target user ID and name from command."""
    # Check if replying to a message
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        return target_user.id, target_user.first_name

    # Check command args for user_id or @username
    # This is a simplified version - full implementation would parse mentions
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []

    if args and args[0].isdigit():
        user_id = int(args[0])
        return user_id, str(user_id)

    return None


@router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    """Ban user from chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply(
            "❌ Укажите пользователя: ответьте на его сообщение или укажите ID.\n"
            "Пример: <code>/ban @user 1д причина</code>"
        )
        return

    target_user_id, target_name = target

    # Parse arguments
    args = message.text.split()[1:]
    if message.reply_to_message:
        args = args  # All args are time and reason
    else:
        args = args[1:]  # Skip user ID/mention

    # Parse time and reason
    duration_seconds = None
    reason = "Не указана"

    if args:
        # Try to parse first arg as time
        time_result = parse_time(args[0])
        if time_result:
            duration_seconds = time_result
            reason = " ".join(args[1:]) if len(args) > 1 else "Не указана"
        else:
            reason = " ".join(args)

    # Ban user
    try:
        if duration_seconds:
            until_date = message.date + timedelta(seconds=duration_seconds)
            await bot.ban_chat_member(chat_id, target_user_id, until_date=until_date)
        else:
            await bot.ban_chat_member(chat_id, target_user_id)

        # Record sanction
        await models.add_sanction(
            chat_id, target_user_id, moderator_id,
            "ban", reason, duration_seconds
        )

        # Send confirmation
        duration_text = format_duration(duration_seconds) if duration_seconds else "навсегда"
        await message.answer(
            f'🔒 <b>Бан</b>: <a href="tg://user?id={target_user_id}">{target_name}</a> — на <b>{duration_text}</b>.\n'
            f'📝 Причина: {reason}\n'
            f'👮 Модератор: {message.from_user.first_name}'
        )

        logger.info("user_banned", chat_id=chat_id, user_id=target_user_id, duration=duration_seconds)

    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("mute"))
async def cmd_mute(message: Message, bot: Bot):
    """Mute user in chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply(
            "❌ Укажите пользователя и время.\n"
            "Пример: <code>/mute @user 50м причина</code>"
        )
        return

    target_user_id, target_name = target

    # Parse arguments
    args = message.text.split()[1:]
    if message.reply_to_message:
        args = args
    else:
        args = args[1:]

    if not args:
        await message.reply("❌ Укажите время мута.\nПример: <code>/mute @user 50м</code>")
        return

    # Parse time
    duration_seconds = parse_time(args[0])
    if not duration_seconds:
        await message.reply(
            "❌ Неверный формат времени.\n"
            "Примеры: <code>50м</code>, <code>3ч</code>, <code>2д</code>, <code>1h30m</code>"
        )
        return

    reason = " ".join(args[1:]) if len(args) > 1 else "Не указана"

    # Mute user
    try:
        until_date = message.date + timedelta(seconds=duration_seconds)
        await bot.restrict_chat_member(
            chat_id,
            target_user_id,
            permissions={"can_send_messages": False},
            until_date=until_date
        )

        # Record sanction
        await models.add_sanction(
            chat_id, target_user_id, moderator_id,
            "mute", reason, duration_seconds
        )

        # Send confirmation
        duration_text = format_duration(duration_seconds)
        await message.answer(
            f'🔇 <b>Мут</b>: <a href="tg://user?id={target_user_id}">{target_name}</a> — на <b>{duration_text}</b>.\n'
            f'📝 Причина: {reason}\n'
            f'👮 Модератор: {message.from_user.first_name}'
        )

        logger.info("user_muted", chat_id=chat_id, user_id=target_user_id, duration=duration_seconds)

    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("warn"))
async def cmd_warn(message: Message):
    """Warn user."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply(
            "❌ Укажите пользователя: ответьте на его сообщение или укажите ID.\n"
            "Пример: <code>/warn @user причина</code>"
        )
        return

    target_user_id, target_name = target

    # Parse reason
    args = message.text.split()[1:]
    if not message.reply_to_message and args:
        args = args[1:]
    reason = " ".join(args) if args else "Не указана"

    # Add warn
    await models.add_sanction(chat_id, target_user_id, moderator_id, "warn", reason)

    # Get total warns
    warn_count = await models.get_warn_count(chat_id, target_user_id)

    # Send confirmation
    await message.answer(
        f'⚠️ <b>Предупреждение</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
        f'📝 Причина: {reason}\n'
        f'👮 Модератор: {message.from_user.first_name}\n'
        f'📊 Всего предупреждений: <b>{warn_count}</b>'
    )

    logger.info("user_warned", chat_id=chat_id, user_id=target_user_id, warn_count=warn_count)

    # TODO: Check warn threshold and apply escalation


@router.message(Command("kick"))
async def cmd_kick(message: Message, bot: Bot):
    """Kick user from chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя для кика.")
        return

    target_user_id, target_name = target

    # Parse reason
    args = message.text.split()[1:]
    if not message.reply_to_message and args:
        args = args[1:]
    reason = " ".join(args) if args else "Не указана"

    # Kick user (ban and immediately unban)
    try:
        await bot.ban_chat_member(chat_id, target_user_id)
        await bot.unban_chat_member(chat_id, target_user_id)

        # Record sanction
        await models.add_sanction(chat_id, target_user_id, moderator_id, "kick", reason)

        await message.answer(
            f'👢 <b>Кик</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
            f'📝 Причина: {reason}\n'
            f'👮 Модератор: {message.from_user.first_name}'
        )

        logger.info("user_kicked", chat_id=chat_id, user_id=target_user_id)

    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    """Unban user from chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя для разбана.")
        return

    target_user_id, target_name = target

    try:
        await bot.unban_chat_member(chat_id, target_user_id, only_if_banned=True)
        await message.answer(
            f'✅ <b>Разбан</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
            f'👮 Модератор: {message.from_user.first_name}'
        )
        logger.info("user_unbanned", chat_id=chat_id, user_id=target_user_id)
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    """Unmute user in chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя для размута.")
        return

    target_user_id, target_name = target

    try:
        # Restore full permissions
        await bot.restrict_chat_member(
            chat_id,
            target_user_id,
            permissions={
                "can_send_messages": True,
                "can_send_media_messages": True,
                "can_send_polls": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True,
                "can_invite_users": True,
                "can_change_info": True,
                "can_pin_messages": True
            }
        )
        await message.answer(
            f'✅ <b>Размут</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
            f'👮 Модератор: {message.from_user.first_name}'
        )
        logger.info("user_unmuted", chat_id=chat_id, user_id=target_user_id)
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message):
    """Remove warning from user."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя для снятия предупреждения.")
        return

    target_user_id, target_name = target

    # Remove last warn
    removed = await models.remove_last_warn(chat_id, target_user_id)

    if removed:
        # Get remaining warns
        warn_count = await models.get_warn_count(chat_id, target_user_id)

        await message.answer(
            f'✅ <b>Предупреждение снято</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
            f'👮 Модератор: {message.from_user.first_name}\n'
            f'📊 Осталось предупреждений: <b>{warn_count}</b>'
        )
        logger.info("warn_removed", chat_id=chat_id, user_id=target_user_id, remaining=warn_count)
    else:
        await message.reply("❌ У пользователя нет активных предупреждений.")


@router.message(Command("addmod"))
async def cmd_addmod(message: Message):
    """Add moderator to chat."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    admin_id = message.from_user.id

    # Check if user is admin or owner
    user_role = await models.get_user_role(chat_id, admin_id)
    if user_role not in ["admin", "owner"] and admin_id not in settings.owner_ids:
        await message.reply("❌ Только администраторы могут назначать модераторов.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя для назначения модератором.")
        return

    target_user_id, target_name = target

    # Add as moderator
    await models.set_user_role(chat_id, target_user_id, "moderator")

    await message.answer(
        f'👮 <b>Модератор назначен</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
        f'👑 Назначил: {message.from_user.first_name}'
    )
    logger.info("moderator_added", chat_id=chat_id, user_id=target_user_id)


@router.message(Command("delmod"))
async def cmd_delmod(message: Message):
    """Remove moderator from chat."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    admin_id = message.from_user.id

    # Check if user is admin or owner
    user_role = await models.get_user_role(chat_id, admin_id)
    if user_role not in ["admin", "owner"] and admin_id not in settings.owner_ids:
        await message.reply("❌ Только администраторы могут снимать модераторов.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите модератора для снятия полномочий.")
        return

    target_user_id, target_name = target

    # Check if user is moderator
    target_role = await models.get_user_role(chat_id, target_user_id)
    if target_role != "moderator":
        await message.reply("❌ Этот пользователь не является модератором.")
        return

    # Remove moderator role
    await models.remove_user_role(chat_id, target_user_id)

    await message.answer(
        f'❌ <b>Модератор снят</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
        f'👑 Снял: {message.from_user.first_name}'
    )
    logger.info("moderator_removed", chat_id=chat_id, user_id=target_user_id)


@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message):
    """Add admin to chat."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    owner_id = message.from_user.id

    # Check if user is owner
    user_role = await models.get_user_role(chat_id, owner_id)
    if user_role != "owner" and owner_id not in settings.owner_ids:
        await message.reply("❌ Только владельцы могут назначать администраторов.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя для назначения администратором.")
        return

    target_user_id, target_name = target

    # Add as admin
    await models.set_user_role(chat_id, target_user_id, "admin")

    await message.answer(
        f'👑 <b>Администратор назначен</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
        f'👑 Назначил: {message.from_user.first_name}'
    )
    logger.info("admin_added", chat_id=chat_id, user_id=target_user_id)


@router.message(Command("deladmin"))
async def cmd_deladmin(message: Message):
    """Remove admin from chat."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    owner_id = message.from_user.id

    # Check if user is owner
    user_role = await models.get_user_role(chat_id, owner_id)
    if user_role != "owner" and owner_id not in settings.owner_ids:
        await message.reply("❌ Только владельцы могут снимать администраторов.")
        return

    # Get target user
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите администратора для снятия полномочий.")
        return

    target_user_id, target_name = target

    # Check if user is admin
    target_role = await models.get_user_role(chat_id, target_user_id)
    if target_role != "admin":
        await message.reply("❌ Этот пользователь не является администратором.")
        return

    # Remove admin role
    await models.remove_user_role(chat_id, target_user_id)

    await message.answer(
        f'❌ <b>Администратор снят</b>: <a href="tg://user?id={target_user_id}">{target_name}</a>\n'
        f'👑 Снял: {message.from_user.first_name}'
    )
    logger.info("admin_removed", chat_id=chat_id, user_id=target_user_id)


@router.message(Command("pin"))
async def cmd_pin(message: Message, bot: Bot):
    """Pin message in chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions (admins only)
    user_role = await models.get_user_role(chat_id, moderator_id)
    if user_role not in ["admin", "owner"] and moderator_id not in settings.owner_ids:
        await message.reply("❌ Только администраторы могут закреплять сообщения.")
        return

    # Check if replying to a message
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение, которое нужно закрепить.")
        return

    try:
        await bot.pin_chat_message(chat_id, message.reply_to_message.message_id, disable_notification=True)
        await message.answer("📌 Сообщение закреплено.")
        logger.info("message_pinned", chat_id=chat_id, message_id=message.reply_to_message.message_id)
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("unpin"))
async def cmd_unpin(message: Message, bot: Bot):
    """Unpin message in chat."""
    if message.chat.type == "private":
        return

    # Check if it's a supergroup
    if message.chat.type != "supergroup":
        await message.reply(
            "❌ Эта команда работает только в супергруппах.\n\n"
            "💡 Преобразуйте группу в супергруппу через настройки группы."
        )
        return

    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Check permissions
    if not await is_moderator(chat_id, moderator_id):
        await message.reply("❌ У вас нет прав на выполнение этой команды.")
        return

    try:
        # If replying to a message, unpin that specific message
        if message.reply_to_message:
            await bot.unpin_chat_message(chat_id, message.reply_to_message.message_id)
        else:
            # Otherwise unpin all messages
            await bot.unpin_all_chat_messages(chat_id)
        await message.answer("🔓 Сообщение откреплено.")
        logger.info("message_unpinned", chat_id=chat_id)
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")


@router.message(Command("giveaway"))
async def cmd_giveaway(message: Message, bot: Bot):
    """Create giveaway (owner only)."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check if user is owner
    user_role = await models.get_user_role(chat_id, user_id)
    if user_role != "owner" and user_id not in settings.owner_ids:
        await message.reply("❌ Только владельцы могут создавать розыгрыши.")
        return

    # Get bot info for deep-link
    bot_info = await bot.me()
    bot_username = bot_info.username

    # Create deep-link to start giveaway wizard
    deep_link = f"https://t.me/{bot_username}?start=giveaway_{chat_id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Создать розыгрыш", url=deep_link)]
    ])

    await message.reply(
        "🎁 <b>Создание розыгрыша</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть мастер создания розыгрыша в личных сообщениях с ботом:",
        reply_markup=keyboard
    )

    logger.info("giveaway_link_sent", chat_id=chat_id, user_id=user_id)


@router.message(Command("settings"))
async def cmd_settings(message: Message, bot: Bot):
    """Open chat settings via deep-link to private messages."""
    if message.chat.type == "private":
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check if user is admin
    if not await is_moderator(chat_id, user_id):
        await message.reply("❌ У вас нет прав для доступа к настройкам.")
        return

    # Get bot info to build deep-link
    bot_info = await bot.me()
    bot_username = bot_info.username

    # Generate deep-link
    deep_link = create_settings_deep_link(bot_username, chat_id)

    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Открыть настройки", url=deep_link)]
    ])

    await message.reply(
        "⚙️ <b>Настройки чата</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть настройки в личных сообщениях с ботом:",
        reply_markup=keyboard
    )

    logger.info("settings_link_sent", chat_id=chat_id, user_id=user_id)


def format_duration(seconds: int) -> str:
    """Format duration in human-readable format."""
    if not seconds:
        return "навсегда"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")

    return " ".join(parts) if parts else f"{seconds}с"
