"""
Rules editor with FSM - allows editing chat rules in private messages.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import structlog
import re

from bot.database import models
from bot.handlers.private.states import RulesEditor

logger = structlog.get_logger(__name__)
router = Router(name="rules_editor")


def validate_html(text: str) -> tuple[bool, str]:
    """
    Validate HTML tags in text.
    Only allow: b, i, u, code, a, pre

    Returns:
        (is_valid, error_message)
    """
    # Allowed tags
    allowed_tags = {'b', 'i', 'u', 'code', 'a', 'pre', 's', 'strike', 'tg-spoiler'}

    # Find all tags
    tag_pattern = r'</?(\w+)[^>]*>'
    tags = re.findall(tag_pattern, text)

    for tag in tags:
        if tag.lower() not in allowed_tags:
            return False, f"Недопустимый тег: <{tag}>"

    # Check for unclosed tags
    stack = []
    for match in re.finditer(r'<(/?)(\w+)[^>]*>', text):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()

        if is_closing:
            if not stack or stack[-1] != tag_name:
                return False, f"Непарный закрывающий тег: </{tag_name}>"
            stack.pop()
        else:
            # Self-closing tags or tags that don't need closing
            if tag_name not in ['br', 'hr']:
                stack.append(tag_name)

    if stack:
        return False, f"Незакрытый тег: <{stack[-1]}>"

    return True, ""


@router.callback_query(F.data.regexp(r'^chat_(-?\d+)_rules$'))
async def open_rules_editor(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Open rules editor for specific chat."""
    # Extract chat_id from callback data
    match = re.match(r'^chat_(-?\d+)_rules$', callback.data)
    chat_id = int(match.group(1))

    # Get current rules
    settings = await models.get_chat_settings(chat_id)
    current_rules = settings.get("rules", {}).get("custom_text")

    if not current_rules:
        # Use default rules
        current_rules = """<b>『 𝔾𝕄 𝕊ℍ𝕆ℙ 』 — ПРАВИЛА ЧАТА</b>

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

    # Get chat title
    try:
        chat = await bot.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = f"Чат {chat_id}"

    # Show current rules
    preview_text = f"📜 <b>Правила чата «{chat_title}»</b>\n\n"
    preview_text += "Текущий текст правил:\n\n"
    preview_text += "─────────────────\n"
    preview_text += current_rules[:500]  # First 500 chars
    if len(current_rules) > 500:
        preview_text += "..."
    preview_text += "\n─────────────────\n\n"
    preview_text += "<i>Выберите действие:</i>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_rules_{chat_id}")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data=f"preview_rules_{chat_id}")],
        [InlineKeyboardButton(text="↩️ Сброс к дефолту", callback_data=f"reset_rules_{chat_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_chat_{chat_id}")]
    ])

    await callback.message.edit_text(preview_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r'^edit_rules_(-?\d+)$'))
async def start_editing_rules(callback: CallbackQuery, state: FSMContext):
    """Start editing rules text."""
    match = re.match(r'^edit_rules_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    await state.set_state(RulesEditor.editing)
    await state.update_data(chat_id=chat_id)

    instruction_text = """✏️ <b>Редактирование правил</b>

Отправьте новый текст правил. Вы можете использовать HTML-разметку:
• <code>&lt;b&gt;жирный&lt;/b&gt;</code> — <b>жирный</b>
• <code>&lt;i&gt;курсив&lt;/i&gt;</code> — <i>курсив</i>
• <code>&lt;u&gt;подчёркнутый&lt;/u&gt;</code> — <u>подчёркнутый</u>
• <code>&lt;code&gt;код&lt;/code&gt;</code> — <code>код</code>
• <code>&lt;a href="url"&gt;ссылка&lt;/a&gt;</code>

Отправьте /cancel для отмены."""

    cancel_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_edit_{chat_id}")]
    ])

    await callback.message.edit_text(instruction_text, reply_markup=cancel_button)
    await callback.answer()


@router.message(RulesEditor.editing)
async def save_rules_text(message: Message, state: FSMContext, bot: Bot):
    """Save new rules text."""
    data = await state.get_data()
    chat_id = data.get("chat_id")

    new_text = message.text

    # Validate HTML
    is_valid, error = validate_html(new_text)
    if not is_valid:
        await message.answer(
            f"❌ <b>Ошибка в разметке</b>\n\n{error}\n\n"
            "Пожалуйста, исправьте и отправьте снова, или отправьте /cancel для отмены."
        )
        return

    # Save to database
    settings = await models.get_chat_settings(chat_id)
    if "rules" not in settings:
        settings["rules"] = {}
    settings["rules"]["custom_text"] = new_text

    await models.update_chat_settings(chat_id, settings)

    # Get chat title
    try:
        chat = await bot.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = f"Чат {chat_id}"

    await message.answer(
        f"✅ <b>Правила сохранены!</b>\n\n"
        f"Правила для чата «{chat_title}» успешно обновлены."
    )

    await state.clear()
    logger.info("rules_updated", chat_id=chat_id, user_id=message.from_user.id)


@router.callback_query(F.data.regexp(r'^preview_rules_(-?\d+)$'))
async def preview_rules(callback: CallbackQuery, bot: Bot):
    """Show rules preview."""
    match = re.match(r'^preview_rules_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    # Get current rules
    settings = await models.get_chat_settings(chat_id)
    rules_text = settings.get("rules", {}).get("custom_text")

    if not rules_text:
        rules_text = "<i>Используются правила по умолчанию</i>"

    preview_text = "👁 <b>Предпросмотр правил</b>\n\n"
    preview_text += "─────────────────\n"
    preview_text += rules_text
    preview_text += "\n─────────────────"

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"chat_{chat_id}_rules")]
    ])

    await callback.message.edit_text(preview_text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data.regexp(r'^reset_rules_(-?\d+)$'))
async def reset_rules(callback: CallbackQuery):
    """Reset rules to default."""
    match = re.match(r'^reset_rules_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    # Remove custom rules from settings
    settings = await models.get_chat_settings(chat_id)
    if "rules" in settings and "custom_text" in settings["rules"]:
        del settings["rules"]["custom_text"]
        await models.update_chat_settings(chat_id, settings)

    await callback.answer("✅ Правила сброшены к дефолту", show_alert=True)

    # Return to rules editor
    await callback.message.edit_text(
        "✅ Правила сброшены к значениям по умолчанию",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data=f"chat_{chat_id}_rules")]
        ])
    )

    logger.info("rules_reset", chat_id=chat_id, user_id=callback.from_user.id)


@router.callback_query(F.data.regexp(r'^cancel_edit_(-?\d+)$'))
async def cancel_editing(callback: CallbackQuery, state: FSMContext):
    """Cancel editing."""
    match = re.match(r'^cancel_edit_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    await state.clear()
    await callback.answer("❌ Редактирование отменено")

    # Return to rules editor
    await callback.message.edit_text(
        "❌ Редактирование отменено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data=f"chat_{chat_id}_rules")]
        ])
    )


@router.callback_query(F.data.regexp(r'^back_to_chat_(-?\d+)$'))
async def back_to_chat_menu(callback: CallbackQuery, bot: Bot):
    """Return to chat settings menu."""
    match = re.match(r'^back_to_chat_(-?\d+)$', callback.data)
    chat_id = int(match.group(1))

    # Get chat title
    try:
        chat = await bot.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = f"Чат {chat_id}"

    # Import here to avoid circular import
    from bot.handlers.private.admin_panel import get_chat_menu_keyboard

    await callback.message.edit_text(
        f"⚙️ <b>Настройки чата «{chat_title}»</b>\n\n"
        "Выберите раздел для настройки:",
        reply_markup=get_chat_menu_keyboard(chat_id)
    )
    await callback.answer()
