"""
User commands handlers (/rules, /karma, /profile, etc.)
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import structlog
import os

from bot.database import models
from bot.config import DEFAULT_CHAT_SETTINGS

logger = structlog.get_logger(__name__)
router = Router(name="user_commands")

# Paths to photos
RULES_PHOTO_PATH = "/app/photo/rules.JPEG"
KARMA_PHOTO_PATH = "/app/photo/karm.JPEG"
PROFILE_PHOTO_PATH = "/app/photo/prof.JPEG"
TOP_PHOTO_PATH = "/app/photo/top.JPEG"


@router.message(Command("rules"))
async def cmd_rules(message: Message):
    """Show chat rules."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id
    settings = await models.get_chat_settings(chat_id)

    # Get custom rules text or use default
    rules_text = settings.get("rules", {}).get("custom_text")

    if not rules_text:
        # Default rules from specification
        rules_text = """<b>『 𝔾𝕄 𝕊ℍ𝕆ℙ 』 — ПРАВИЛА ЧАТА</b>

🚫 <b>Флуд и спам</b>: более 6 сообщений <i>подряд</i> — <b>мут на 50 минут</b>.
🚫 <b>Личные оскорбления, унижения</b> — строго запрещены.
🚫 <b>18+ контент</b> — запрещён.
🚫 <b>Флуд реакциями/стикерами/гиф</b> — ограничен (в разумных пределах).
🚫 <b>Обильная ненормативная лексика</b> — запрещена.
🚫 <b>Оскорбления администрации</b> — запрещены.
🚫 <b>Затрагивание религии</b> в оскорбительной форме — запрещено.
🚫 <b>Неадекватные стикеры</b> — запрещены.
🚫 <b>Политика</b> — вне чата (обсуждение запрещено).
🚫 <b>Заработок/ставки/казино</b> и подобные «оферы» — запрещены (автомут).

⚠️ При неадекватной реакции на мнение администрации — <b>предупреждение</b> либо <b>бан на 1 день</b> по усмотрению модератора.
🤖 При использовании развлекательных ботов — соблюдайте нормы морали. Аморальщина и спам шаблонами запрещены.

<b>UPD:</b> Правила распространяются на <b>всех</b> участников без исключений."""

    # Send rules with photo
    try:
        if os.path.exists(RULES_PHOTO_PATH):
            photo = FSInputFile(RULES_PHOTO_PATH)
            await message.answer_photo(
                photo=photo,
                caption=rules_text
            )
        else:
            # Fallback to text if photo not found
            await message.answer(rules_text)
            logger.warning("rules_photo_not_found", path=RULES_PHOTO_PATH)
    except Exception as e:
        logger.error("failed_to_send_rules", error=str(e))
        # Fallback to text message
        await message.answer(rules_text)


@router.message(Command("karma"))
async def cmd_karma(message: Message):
    """Show user karma."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id

    # Check if karma is enabled
    settings = await models.get_chat_settings(chat_id)
    if not settings.get("karma", {}).get("enabled", True):
        return

    # Check if replying to someone or checking own karma
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        user_id = message.from_user.id

    # Get display name (nickname or first name)
    display_name = await models.get_display_name(chat_id, user_id)

    # Get karma
    karma = await models.get_karma(chat_id, user_id)

    karma_emoji = "⭐" if karma >= 0 else "💀"
    karma_text = f'{karma_emoji} <b>Карма</b> <a href="tg://user?id={user_id}">{display_name}</a>: <b>{karma}</b>'

    # Send karma with photo
    try:
        if os.path.exists(KARMA_PHOTO_PATH):
            photo = FSInputFile(KARMA_PHOTO_PATH)
            await message.answer_photo(photo=photo, caption=karma_text)
        else:
            await message.answer(karma_text)
            logger.warning("karma_photo_not_found", path=KARMA_PHOTO_PATH)
    except Exception as e:
        logger.error("failed_to_send_karma", error=str(e))
        await message.answer(karma_text)


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Show user profile."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Get user stats
    member = await models.get_or_create_chat_member(chat_id, user_id)

    # Get display name
    display_name = await models.get_display_name(chat_id, user_id)

    # Get user settings
    user_data = await models.db.fetchrow(
        "SELECT disable_weekly_top_mention FROM users WHERE user_id = $1",
        user_id
    )
    disable_mention = user_data.get('disable_weekly_top_mention', False) if user_data else False

    # Check if user has nickname
    nickname = member.get('nickname')
    nickname_text = f"\n🏷 Прозвище: <b>{nickname}</b>" if nickname else ""

    # Format join date
    joined_at = member.get("joined_at")
    if joined_at:
        joined_str = joined_at.strftime("%d.%m.%Y")
    else:
        joined_str = "Неизвестно"

    # Status of notifications
    notify_status = "🔕 Выключены" if disable_mention else "🔔 Включены"

    profile_text = f"""👤 <b>Профиль:</b> <a href="tg://user?id={user_id}">{display_name}</a>{nickname_text}

📅 В чате с: <b>{joined_str}</b>
💬 Сообщений за неделю: <b>{member.get('messages_week', 0)}</b>
⭐ Карма: <b>{member.get('karma', 0)}</b>

⚙️ Уведомления в топе недели: <b>{notify_status}</b>
"""

    # Create inline keyboard
    button_text = "🔕 Выключить уведомления" if not disable_mention else "🔔 Включить уведомления"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data=f"toggle_weekly_mention:{user_id}")]
    ])

    # Send profile with photo
    try:
        if os.path.exists(PROFILE_PHOTO_PATH):
            photo = FSInputFile(PROFILE_PHOTO_PATH)
            await message.answer_photo(photo=photo, caption=profile_text, reply_markup=keyboard)
        else:
            await message.answer(profile_text, reply_markup=keyboard)
            logger.warning("profile_photo_not_found", path=PROFILE_PHOTO_PATH)
    except Exception as e:
        logger.error("failed_to_send_profile", error=str(e))
        await message.answer(profile_text, reply_markup=keyboard)


@router.message(Command("top"))
async def cmd_top(message: Message):
    """Show weekly top."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id

    # Get top 10 by messages (7d)
    top_users = await models.get_top_by_messages(chat_id, limit=10)

    if not top_users:
        top_text = "📊 <b>Топ недели</b>\n\n🔜 Пока нет данных за эту неделю.\n\n<i>Будь активным и попади в топ!</i>"
    else:
        top_lines = []
        for i, user in enumerate(top_users, 1):
            user_id = user['user_id']
            msg_count = user['messages_week']
            # Get display name (nickname or first name)
            display_name = await models.get_display_name(chat_id, user_id)

            # Medals for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."

            top_lines.append(f"{medal} <a href=\"tg://user?id={user_id}\">{display_name}</a> — <b>{msg_count}</b> сообщений")

        top_text = "📊 <b>Топ недели</b>\n\n" + "\n".join(top_lines)

    # Send with photo
    try:
        if os.path.exists(TOP_PHOTO_PATH):
            photo = FSInputFile(TOP_PHOTO_PATH)
            await message.answer_photo(photo=photo, caption=top_text)
        else:
            await message.answer(top_text)
            logger.warning("top_photo_not_found", path=TOP_PHOTO_PATH)
    except Exception as e:
        logger.error("failed_to_send_top", error=str(e))
        await message.answer(top_text)


@router.callback_query(F.data.startswith("toggle_weekly_mention:"))
async def callback_toggle_weekly_mention(callback: CallbackQuery):
    """Toggle weekly top mention notification setting."""
    # Extract user_id from callback data
    user_id_from_data = int(callback.data.split(":")[1])

    # Security check - only user themselves can toggle their setting
    if callback.from_user.id != user_id_from_data:
        await callback.answer("❌ Вы можете изменить только свои настройки!", show_alert=True)
        return

    user_id = callback.from_user.id

    # Get current setting
    user_data = await models.db.fetchrow(
        "SELECT disable_weekly_top_mention FROM users WHERE user_id = $1",
        user_id
    )

    if user_data:
        # Toggle setting
        current_value = user_data.get('disable_weekly_top_mention', False)
        new_value = not current_value

        await models.db.execute(
            "UPDATE users SET disable_weekly_top_mention = $1 WHERE user_id = $2",
            new_value, user_id
        )

        # Send confirmation
        if new_value:
            await callback.answer("🔕 Уведомления в топе недели выключены", show_alert=True)
        else:
            await callback.answer("🔔 Уведомления в топе недели включены", show_alert=True)

        logger.info("weekly_mention_toggled", user_id=user_id, new_value=new_value)

        # Update message
        # Get updated data
        chat_id = callback.message.chat.id
        member = await models.get_or_create_chat_member(chat_id, user_id)
        display_name = await models.get_display_name(chat_id, user_id)

        nickname = member.get('nickname')
        nickname_text = f"\n🏷 Прозвище: <b>{nickname}</b>" if nickname else ""

        joined_at = member.get("joined_at")
        if joined_at:
            joined_str = joined_at.strftime("%d.%m.%Y")
        else:
            joined_str = "Неизвестно"

        notify_status = "🔕 Выключены" if new_value else "🔔 Включены"

        profile_text = f"""👤 <b>Профиль:</b> <a href="tg://user?id={user_id}">{display_name}</a>{nickname_text}

📅 В чате с: <b>{joined_str}</b>
💬 Сообщений за неделю: <b>{member.get('messages_week', 0)}</b>
⭐ Карма: <b>{member.get('karma', 0)}</b>

⚙️ Уведомления в топе недели: <b>{notify_status}</b>
"""

        # Update keyboard
        button_text = "🔕 Выключить уведомления" if not new_value else "🔔 Включить уведомления"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data=f"toggle_weekly_mention:{user_id}")]
        ])

        try:
            await callback.message.edit_caption(caption=profile_text, reply_markup=keyboard)
        except Exception:
            # If it's a text message, not a photo
            try:
                await callback.message.edit_text(text=profile_text, reply_markup=keyboard)
            except Exception as e:
                logger.error("failed_to_update_profile_message", error=str(e))

    else:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
