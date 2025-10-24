"""
Welcome message editor with FSM - allows editing welcome messages in private messages.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import structlog
import re

from bot.database import models
from bot.handlers.private.states import WelcomeEditor
from bot.handlers.private.rules_editor import validate_html

logger = structlog.get_logger(__name__)
router = Router(name="welcome_editor")


@router.callback_query(F.data.regexp(r'^chat_(-?\d+)_welcome$'))
async def open_welcome_editor(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Open welcome message editor for specific chat."""
    match = re.match(r'^chat_(-?\d+)_welcome$', callback.data)
    chat_id = int(match.group(1))

    # Get current welcome settings
    settings = await models.get_chat_settings(chat_id)
    welcome_settings = settings.get("welcome", {})

    current_text = welcome_settings.get("custom_text")
    enabled = welcome_settings.get("enabled", True)
    auto_delete = welcome_settings.get("auto_delete_minutes", 0)

    if not current_text:
        # Use default welcome
        current_text = """<b>Приветствуем, {first_name} 👋 в магазине «GM SHOP»!</b>

🛒 Здесь ты найдёшь <b>самый дешёвый донат</b> в игры и <b>лучший сервис</b> на рынке.
❓ По всем вопросам — сразу к администраторам <i>(первыми не пишем)</i>.
🎁 Желаем приятного отдыха и выгодных покупок!

📜 <b>Правила чата:</b> набери /rules — обязательно ознакомься."""

    # Get chat title
    try:
        chat = await bot.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = f"Чат {chat_id}"

    status_emoji = "✅" if enabled else "❌"
    auto_delete_text = f"{auto_delete} мин" if auto_delete > 0 else "Выключено"

    # Show current welcome
    preview_text = f"👋 <b>Приветствие для чата «{chat_title}»</b>\n\n"
    preview_text += f"Статус: {status_emoji} {'Включено' if enabled else 'Выключено'}\n"
    preview_text += f"Автоудаление: {auto_delete_text}\n\n"
    preview_text += "Текущий текст:\n"
    preview_text += "─────────────────\n"
    preview_text += current_text[:400]
    if len(current_text) > 400:
        preview_text += "..."
    preview_text += "\n─────────────────\n\n"
    preview_text += "<b>Доступные плейсхолдеры:</b>\n"
    preview_text += "<code>{user_id}</code> - ID пользователя\n"
    preview_text += "<code>{first_name}</code> - Имя\n"
    preview_text += "<code>{username}</code> - Username\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"edit_welcome_text_{chat_id}")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data=f"preview_welcome_{chat_id}")],
        [
            InlineKeyboardButton(
                text=f"{'✅' if enabled else '❌'} Вкл/Выкл",
                callback_data=f"toggle_welcome_{chat_id}"
            )
        ],
        [InlineKeyboardButton(text="🕐 Автоудаление", callback_data=f"edit_autodelete_{chat_id}")],
        [InlineKeyboardButton(text="↩️ Сброс к дефолту", callback_data=f"reset_welcome_{chat_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_chat_{chat_id}")]
    ])

    await callback.message.edit_text(preview_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r'^edit_welcome_text_(-?\d+)$'))
async def start_editing_welcome(callback: CallbackQuery, state: FSMContext):
    """Start editing welcome text."""
    match = re.match(r'^edit_welcome_text_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    await state.set_state(WelcomeEditor.editing_text)
    await state.update_data(chat_id=chat_id)

    instruction_text = """✏️ <b>Редактирование приветствия</b>

Отправьте новый текст приветствия. Вы можете использовать:

<b>HTML-разметку:</b>
• <code>&lt;b&gt;жирный&lt;/b&gt;</code>
• <code>&lt;i&gt;курсив&lt;/i&gt;</code>
• <code>&lt;u&gt;подчёркнутый&lt;/u&gt;</code>
• <code>&lt;code&gt;код&lt;/code&gt;</code>

<b>Плейсхолдеры:</b>
• <code>{user_id}</code> - ID пользователя
• <code>{first_name}</code> - Имя пользователя
• <code>{username}</code> - Username (или имя)

Отправьте /cancel для отмены."""

    cancel_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_edit_welcome_{chat_id}")]
    ])

    await callback.message.edit_text(instruction_text, reply_markup=cancel_button)
    await callback.answer()


@router.message(WelcomeEditor.editing_text)
async def save_welcome_text(message: Message, state: FSMContext, bot: Bot):
    """Save new welcome text."""
    data = await state.get_data()
    chat_id = data.get("chat_id")

    new_text = message.text

    # Validate HTML
    # Replace placeholders temporarily for validation
    temp_text = new_text.replace("{user_id}", "123")
    temp_text = temp_text.replace("{first_name}", "User")
    temp_text = temp_text.replace("{username}", "user")

    is_valid, error = validate_html(temp_text)
    if not is_valid:
        await message.answer(
            f"❌ <b>Ошибка в разметке</b>\n\n{error}\n\n"
            "Пожалуйста, исправьте и отправьте снова, или отправьте /cancel для отмены."
        )
        return

    # Save to database
    settings = await models.get_chat_settings(chat_id)
    if "welcome" not in settings:
        settings["welcome"] = {}
    settings["welcome"]["custom_text"] = new_text

    await models.update_chat_settings(chat_id, settings)

    # Get chat title
    try:
        chat = await bot.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = f"Чат {chat_id}"

    await message.answer(
        f"✅ <b>Приветствие сохранено!</b>\n\n"
        f"Приветствие для чата «{chat_title}» успешно обновлено."
    )

    await state.clear()
    logger.info("welcome_updated", chat_id=chat_id, user_id=message.from_user.id)


@router.callback_query(F.data.regexp(r'^preview_welcome_(-?\d+)$'))
async def preview_welcome(callback: CallbackQuery, bot: Bot):
    """Show welcome preview with sample data."""
    match = re.match(r'^preview_welcome_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    # Get current welcome
    settings = await models.get_chat_settings(chat_id)
    welcome_text = settings.get("welcome", {}).get("custom_text")

    if not welcome_text:
        welcome_text = "<i>Используется приветствие по умолчанию</i>"
    else:
        # Format with sample data
        welcome_text = welcome_text.format(
            user_id=callback.from_user.id,
            first_name=callback.from_user.first_name,
            username=callback.from_user.username or callback.from_user.first_name
        )

    preview_text = "👁 <b>Предпросмотр приветствия</b>\n\n"
    preview_text += "─────────────────\n"
    preview_text += welcome_text
    preview_text += "\n─────────────────"

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"chat_{chat_id}_welcome")]
    ])

    await callback.message.edit_text(preview_text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data.regexp(r'^toggle_welcome_(-?\d+)$'))
async def toggle_welcome(callback: CallbackQuery):
    """Toggle welcome message on/off."""
    match = re.match(r'^toggle_welcome_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    settings = await models.get_chat_settings(chat_id)
    if "welcome" not in settings:
        settings["welcome"] = {}

    current_status = settings["welcome"].get("enabled", True)
    settings["welcome"]["enabled"] = not current_status

    await models.update_chat_settings(chat_id, settings)

    new_status = "включено" if not current_status else "выключено"
    await callback.answer(f"✅ Приветствие {new_status}", show_alert=True)

    # Refresh the menu
    from bot.handlers.private.welcome_editor import open_welcome_editor
    await open_welcome_editor(callback, None, callback.bot)

    logger.info("welcome_toggled", chat_id=chat_id, enabled=not current_status)


@router.callback_query(F.data.regexp(r'^edit_autodelete_(-?\d+)$'))
async def start_editing_autodelete(callback: CallbackQuery, state: FSMContext):
    """Start editing auto-delete time."""
    match = re.match(r'^edit_autodelete_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    await state.set_state(WelcomeEditor.editing_auto_delete)
    await state.update_data(chat_id=chat_id)

    instruction_text = """🕐 <b>Автоудаление приветствия</b>

Введите через сколько минут удалять приветствие (0 = отключить):

Примеры:
• <code>5</code> - удалить через 5 минут
• <code>0</code> - не удалять
• <code>60</code> - удалить через час

Отправьте /cancel для отмены."""

    cancel_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_edit_welcome_{chat_id}")]
    ])

    await callback.message.edit_text(instruction_text, reply_markup=cancel_button)
    await callback.answer()


@router.message(WelcomeEditor.editing_auto_delete)
async def save_autodelete_time(message: Message, state: FSMContext, bot: Bot):
    """Save auto-delete time."""
    data = await state.get_data()
    chat_id = data.get("chat_id")

    try:
        minutes = int(message.text)
        if minutes < 0:
            raise ValueError("Negative value")
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите целое число больше или равное 0, или отправьте /cancel для отмены."
        )
        return

    # Save to database
    settings = await models.get_chat_settings(chat_id)
    if "welcome" not in settings:
        settings["welcome"] = {}
    settings["welcome"]["auto_delete_minutes"] = minutes

    await models.update_chat_settings(chat_id, settings)

    if minutes == 0:
        status_text = "отключено"
    else:
        status_text = f"установлено на {minutes} мин"

    await message.answer(f"✅ <b>Автоудаление {status_text}!</b>")

    await state.clear()
    logger.info("welcome_autodelete_updated", chat_id=chat_id, minutes=minutes)


@router.callback_query(F.data.regexp(r'^reset_welcome_(-?\d+)$'))
async def reset_welcome(callback: CallbackQuery):
    """Reset welcome to default."""
    match = re.match(r'^reset_welcome_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    # Remove custom welcome from settings
    settings = await models.get_chat_settings(chat_id)
    if "welcome" in settings and "custom_text" in settings["welcome"]:
        del settings["welcome"]["custom_text"]
        await models.update_chat_settings(chat_id, settings)

    await callback.answer("✅ Приветствие сброшено к дефолту", show_alert=True)

    # Return to welcome editor
    await callback.message.edit_text(
        "✅ Приветствие сброшено к значениям по умолчанию",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data=f"chat_{chat_id}_welcome")]
        ])
    )

    logger.info("welcome_reset", chat_id=chat_id, user_id=callback.from_user.id)


@router.callback_query(F.data.regexp(r'^cancel_edit_welcome_(-?\d+)$'))
async def cancel_editing_welcome(callback: CallbackQuery, state: FSMContext):
    """Cancel editing welcome."""
    match = re.match(r'^cancel_edit_welcome_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    await state.clear()
    await callback.answer("❌ Редактирование отменено")

    # Return to welcome editor
    await callback.message.edit_text(
        "❌ Редактирование отменено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data=f"chat_{chat_id}_welcome")]
        ])
    )
