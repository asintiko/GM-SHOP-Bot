"""
User statistics commands (!стата, !общстат)
"""

from aiogram import Router, F
from aiogram.types import Message
from datetime import datetime, timedelta
import structlog

from bot.database import models

logger = structlog.get_logger(__name__)
router = Router(name="statistics")


@router.message(F.text.lower().in_(["!стата", "!статистика"]))
async def cmd_user_stats(message: Message):
    """Show user messages statistics."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id

    # Determine target user
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        target_user_id = message.from_user.id

    # Get display name (nickname or first name)
    display_name = await models.get_display_name(chat_id, target_user_id)

    # Get user stats from database
    member = await models.get_or_create_chat_member(chat_id, target_user_id)

    # Get messages count
    msg_all = member.get('messages_all_time', 0)

    # Build statistics text
    stats_text = f"""📊 <b>Статистика пользователя</b> <a href="tg://user?id={target_user_id}">{display_name}</a>

💬 <b>Сообщений за все время:</b> <b>{msg_all}</b>"""

    await message.answer(stats_text)
    logger.info("user_stats_shown", chat_id=chat_id, target_user_id=target_user_id)


@router.message(F.text.lower() == "!общстат")
async def cmd_chat_stats(message: Message):
    """Show chat aggregate statistics with top 10."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id
    chat_title = message.chat.title or "этот чат"

    # Get top 10 by messages (7d)
    top_messages_week = await models.get_top_by_messages(chat_id, limit=10)
    top_week_lines = []
    for i, user in enumerate(top_messages_week, 1):
        user_id = user['user_id']
        msg_count = user['messages_week']
        # Get display name (nickname or first name)
        display_name = await models.get_display_name(chat_id, user_id)
        top_week_lines.append(f"{i}. <a href=\"tg://user?id={user_id}\">{display_name}</a> — <b>{msg_count}</b> сообщений")

    top_week_text = "\n".join(top_week_lines) if top_week_lines else "Нет данных"

    # Get top 10 by messages (all time)
    top_messages_all = await models.get_top_by_messages_all_time(chat_id, limit=10)
    top_all_lines = []
    for i, user in enumerate(top_messages_all, 1):
        user_id = user['user_id']
        msg_count = user['messages_all_time']
        # Get display name (nickname or first name)
        display_name = await models.get_display_name(chat_id, user_id)
        top_all_lines.append(f"{i}. <a href=\"tg://user?id={user_id}\">{display_name}</a> — <b>{msg_count}</b> сообщений")

    top_all_text = "\n".join(top_all_lines) if top_all_lines else "Нет данных"

    # Build statistics text with blockquote formatting
    stats_text = f"""🧮 <b>Общая статистика — «{chat_title}»</b>

<blockquote><b>📊 ТОП-10 ЗА НЕДЕЛЮ</b>

{top_week_text}</blockquote>

<blockquote><b>🏆 ТОП-10 ЗА ВСЕ ВРЕМЯ</b>

{top_all_text}</blockquote>"""

    await message.answer(stats_text)
    logger.info("chat_stats_shown", chat_id=chat_id)
