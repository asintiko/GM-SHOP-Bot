"""
Giveaway creation wizard with FSM.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import structlog
import re

from bot.database import models
from bot.handlers.private.states import GiveawayWizard

logger = structlog.get_logger(__name__)
router = Router(name="giveaway_wizard")


@router.callback_query(F.data == "create_giveaway")
async def start_giveaway_wizard(callback: CallbackQuery, state: FSMContext):
    """Start giveaway creation wizard."""
    # For now, use owner's main chat or ask for chat selection
    # This is a simplified version - full implementation would allow chat selection

    await state.set_state(GiveawayWizard.title)

    instruction_text = """🎁 <b>Создание розыгрыша</b>

<b>Шаг 1/5:</b> Название розыгрыша

Введите название (заголовок) вашего розыгрыша.
Например: <i>«Розыгрыш донат на 1000 руб»</i>

Отправьте /cancel для отмены."""

    cancel_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_giveaway")]
    ])

    await callback.message.edit_text(instruction_text, reply_markup=cancel_button)
    await callback.answer()


@router.message(GiveawayWizard.title)
async def process_title(message: Message, state: FSMContext):
    """Process giveaway title."""
    title = message.text

    if len(title) > 200:
        await message.answer("❌ Название слишком длинное. Максимум 200 символов.")
        return

    await state.update_data(title=title)
    await state.set_state(GiveawayWizard.description)

    await message.answer(
        "<b>Шаг 2/5:</b> Описание\n\n"
        "Введите описание розыгрыша. Что разыгрываете? Как участвовать?\n"
        "Можно использовать HTML-разметку.\n\n"
        "Отправьте /cancel для отмены."
    )


@router.message(GiveawayWizard.description)
async def process_description(message: Message, state: FSMContext):
    """Process giveaway description."""
    description = message.text

    if len(description) > 2000:
        await message.answer("❌ Описание слишком длинное. Максимум 2000 символов.")
        return

    await state.update_data(description=description)
    await state.set_state(GiveawayWizard.duration_hours)

    await message.answer(
        "<b>Шаг 3/5:</b> Длительность\n\n"
        "Введите длительность розыгрыша в часах.\n"
        "Например: <code>24</code> (1 день), <code>48</code> (2 дня), <code>168</code> (неделя)\n\n"
        "Отправьте /cancel для отмены."
    )


@router.message(GiveawayWizard.duration_hours)
async def process_duration(message: Message, state: FSMContext):
    """Process giveaway duration."""
    try:
        hours = int(message.text)
        if hours < 1 or hours > 720:  # Max 30 days
            raise ValueError("Invalid range")
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите целое число от 1 до 720 (30 дней)."
        )
        return

    await state.update_data(duration_hours=hours)
    await state.set_state(GiveawayWizard.winners_count)

    await message.answer(
        "<b>Шаг 4/5:</b> Количество победителей\n\n"
        "Введите количество победителей (1-10).\n\n"
        "Отправьте /cancel для отмены."
    )


@router.message(GiveawayWizard.winners_count)
async def process_winners_count(message: Message, state: FSMContext):
    """Process winners count."""
    try:
        count = int(message.text)
        if count < 1 or count > 10:
            raise ValueError("Invalid range")
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите целое число от 1 до 10."
        )
        return

    await state.update_data(winners_count=count)
    await state.set_state(GiveawayWizard.requirements)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без требований", callback_data="no_requirements")]
    ])

    await message.answer(
        "<b>Шаг 5/5:</b> Требования к участникам\n\n"
        "Введите требования для участия (или нажмите кнопку ниже):\n\n"
        "Примеры:\n"
        "• Минимум 10 сообщений за неделю\n"
        "• Карма не ниже 5\n"
        "• Быть в чате не менее 7 дней\n\n"
        "Отправьте /cancel для отмены.",
        reply_markup=keyboard
    )


@router.message(GiveawayWizard.requirements)
async def process_requirements(message: Message, state: FSMContext, bot: Bot):
    """Process requirements and create giveaway."""
    requirements = message.text

    await state.update_data(requirements=requirements)

    # Get all data
    data = await state.get_data()
    chat_id = data.get("chat_id")  # Would be set earlier in full implementation

    # For now, use a placeholder chat_id
    # In production, you'd ask user to select chat or use default
    if not chat_id:
        # Try to get from settings or ask user
        await message.answer(
            "❌ Не указан чат для розыгрыша. Эта функция будет доработана в следующей версии."
        )
        await state.clear()
        return

    # Create giveaway in database
    title = data["title"]
    description = data["description"]
    duration_hours = data["duration_hours"]
    winners_count = data["winners_count"]

    ends_at = datetime.now() + timedelta(hours=duration_hours)

    giveaway_id = await models.db.fetchval(
        """
        INSERT INTO giveaways (chat_id, title, description, ends_at, winners_count, requirements)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        chat_id, title, description, ends_at, winners_count, requirements
    )

    # Schedule notifications (would be handled by scheduler service)
    # For now, just save the giveaway

    # Post announcement to chat
    announcement = f"""🎁 <b>{title}</b>

{description}

<b>Победителей:</b> {winners_count}
<b>Окончание:</b> {ends_at.strftime('%d.%m.%Y %H:%M')} МСК

<b>Требования:</b>
{requirements if requirements else 'Нет требований'}

Нажмите кнопку ниже для участия! 👇"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Участвовать", callback_data=f"join_giveaway_{giveaway_id}")]
    ])

    try:
        await bot.send_message(chat_id, announcement, reply_markup=keyboard)

        await message.answer(
            f"✅ <b>Розыгрыш создан!</b>\n\n"
            f"ID: {giveaway_id}\n"
            f"Окончание: {ends_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Объявление опубликовано в чате."
        )

        logger.info("giveaway_created", giveaway_id=giveaway_id, chat_id=chat_id)

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при публикации объявления: {str(e)}\n"
            f"Розыгрыш сохранён, но не опубликован."
        )
        logger.error("giveaway_post_failed", giveaway_id=giveaway_id, error=str(e))

    await state.clear()


@router.callback_query(F.data == "no_requirements")
async def no_requirements(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Handle 'no requirements' button."""
    await state.update_data(requirements="Нет требований")

    # Get all data
    data = await state.get_data()
    chat_id = data.get("chat_id")

    if not chat_id:
        await callback.message.edit_text(
            "❌ Не указан чат для розыгрыша. Эта функция будет доработана в следующей версии."
        )
        await state.clear()
        await callback.answer()
        return

    # Create giveaway (same logic as above)
    title = data["title"]
    description = data["description"]
    duration_hours = data["duration_hours"]
    winners_count = data["winners_count"]
    requirements = "Нет требований"

    ends_at = datetime.now() + timedelta(hours=duration_hours)

    giveaway_id = await models.db.fetchval(
        """
        INSERT INTO giveaways (chat_id, title, description, ends_at, winners_count, requirements)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        chat_id, title, description, ends_at, winners_count, requirements
    )

    announcement = f"""🎁 <b>{title}</b>

{description}

<b>Победителей:</b> {winners_count}
<b>Окончание:</b> {ends_at.strftime('%d.%m.%Y %H:%M')} МСК

✅ Участвовать могут все!

Нажмите кнопку ниже для участия! 👇"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Участвовать", callback_data=f"join_giveaway_{giveaway_id}")]
    ])

    try:
        await bot.send_message(chat_id, announcement, reply_markup=keyboard)

        await callback.message.edit_text(
            f"✅ <b>Розыгрыш создан!</b>\n\n"
            f"ID: {giveaway_id}\n"
            f"Окончание: {ends_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Объявление опубликовано в чате."
        )

        logger.info("giveaway_created", giveaway_id=giveaway_id, chat_id=chat_id)

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при публикации объявления: {str(e)}\n"
            f"Розыгрыш сохранён, но не опубликован."
        )
        logger.error("giveaway_post_failed", giveaway_id=giveaway_id, error=str(e))

    await state.clear()
    await callback.answer()


@router.callback_query(F.data.regexp(r'^join_giveaway_(\d+)$'))
async def join_giveaway(callback: CallbackQuery):
    """Handle giveaway participation."""
    match = re.match(r'^join_giveaway_(\d+)$', callback.data)
    giveaway_id = int(match.group(1))

    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    # Check if giveaway exists and is active
    giveaway = await models.db.fetchrow(
        "SELECT * FROM giveaways WHERE id = $1 AND chat_id = $2",
        giveaway_id, chat_id
    )

    if not giveaway:
        await callback.answer("❌ Розыгрыш не найден", show_alert=True)
        return

    if not giveaway["is_active"]:
        await callback.answer("❌ Розыгрыш завершён", show_alert=True)
        return

    if datetime.now() > giveaway["ends_at"]:
        await callback.answer("❌ Розыгрыш закончился", show_alert=True)
        return

    # Check if already participating
    already_joined = await models.db.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM giveaway_entries
            WHERE giveaway_id = $1 AND user_id = $2
        )
        """,
        giveaway_id, user_id
    )

    if already_joined:
        await callback.answer("ℹ️ Вы уже участвуете в этом розыгрыше!", show_alert=True)
        return

    # Add entry
    await models.db.execute(
        """
        INSERT INTO giveaway_entries (giveaway_id, chat_id, user_id)
        VALUES ($1, $2, $3)
        """,
        giveaway_id, chat_id, user_id
    )

    await callback.answer("✅ Вы участвуете в розыгрыше! Удачи! 🍀", show_alert=True)
    logger.info("giveaway_entry_added", giveaway_id=giveaway_id, user_id=user_id)


@router.callback_query(F.data == "cancel_giveaway")
async def cancel_giveaway_wizard(callback: CallbackQuery, state: FSMContext):
    """Cancel giveaway creation."""
    await state.clear()
    await callback.answer("❌ Создание розыгрыша отменено")
    await callback.message.edit_text("❌ Создание розыгрыша отменено")
