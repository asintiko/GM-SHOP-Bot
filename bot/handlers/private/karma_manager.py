"""
Karma management through private messages for admins.
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import structlog

from bot.database import models
from bot.handlers.private.states import Form

logger = structlog.get_logger(__name__)
router = Router(name="karma_manager")


class KarmaForm(StatesGroup):
    """States for karma management."""
    waiting_for_chat = State()
    waiting_for_user = State()
    waiting_for_amount = State()


@router.message(Command("addkarma"))
@router.message(F.text.lower() == "добавить карму")
async def cmd_add_karma(message: Message, state: FSMContext):
    """Start karma addition process."""
    user_id = message.from_user.id
    
    # Get list of chats where user is admin
    chats = await models.db.fetch(
        """
        SELECT c.chat_id, c.title
        FROM chats c
        JOIN staff s ON c.chat_id = s.chat_id
        WHERE s.user_id = $1 AND s.role IN ('admin', 'owner')
        ORDER BY c.title
        """,
        user_id
    )
    
    if not chats:
        await message.answer("❌ Вы не являетесь администратором ни в одном чате.")
        return
    
    # Show chat selection
    chat_list = "\n".join([f"{i+1}. {chat['title']}" for i, chat in enumerate(chats)])
    await state.update_data(chats=chats)
    await state.set_state(KarmaForm.waiting_for_chat)
    
    await message.answer(
        f"<b>📊 Управление кармой</b>\n\n"
        f"Выберите чат (отправьте номер):\n\n{chat_list}"
    )


@router.message(KarmaForm.waiting_for_chat)
async def process_chat_selection(message: Message, state: FSMContext):
    """Process chat selection."""
    try:
        choice = int(message.text.strip())
        data = await state.get_data()
        chats = data.get('chats', [])
        
        if choice < 1 or choice > len(chats):
            await message.answer("❌ Неверный номер чата. Попробуйте снова:")
            return
        
        selected_chat = chats[choice - 1]
        await state.update_data(selected_chat_id=selected_chat['chat_id'], selected_chat_title=selected_chat['title'])
        await state.set_state(KarmaForm.waiting_for_user)
        
        await message.answer(
            f"<b>Выбран чат:</b> {selected_chat['title']}\n\n"
            f"Теперь отправьте username или ID пользователя:"
        )
    except ValueError:
        await message.answer("❌ Отправьте номер чата:")


@router.message(KarmaForm.waiting_for_user)
async def process_user_input(message: Message, state: FSMContext):
    """Process user input (username or ID)."""
    user_input = message.text.strip().lstrip('@')
    
    # Try to find user by username or ID
    if user_input.isdigit():
        user_id = int(user_input)
        user = await models.db.fetchrow(
            "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
            user_id
        )
    else:
        user = await models.db.fetchrow(
            "SELECT user_id, first_name, username FROM users WHERE LOWER(username) = LOWER($1)",
            user_input
        )
    
    if not user:
        await message.answer("❌ Пользователь не найден. Попробуйте снова:")
        return
    
    await state.update_data(target_user_id=user['user_id'], target_user_name=user['first_name'] or user['username'])
    await state.set_state(KarmaForm.waiting_for_amount)
    
    await message.answer(
        f"<b>Выбран пользователь:</b> {user['first_name'] or user['username']}\n\n"
        f"Отправьте количество кармы для добавления (можно отрицательное число для уменьшения):"
    )


@router.message(KarmaForm.waiting_for_amount)
async def process_karma_amount(message: Message, state: FSMContext, bot: Bot):
    """Process karma amount and update."""
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        
        chat_id = data['selected_chat_id']
        chat_title = data['selected_chat_title']
        target_user_id = data['target_user_id']
        target_user_name = data['target_user_name']
        admin_id = message.from_user.id
        
        # Get or create chat and member
        await models.get_or_create_chat(chat_id, chat_title)
        await models.get_or_create_chat_member(chat_id, target_user_id)
        
        # Update karma
        new_karma = await models.update_karma(chat_id, target_user_id, amount)
        
        # Log to admin
        await message.answer(
            f"✅ <b>Карма обновлена!</b>\n\n"
            f"👤 Пользователь: {target_user_name}\n"
            f"💬 Чат: {chat_title}\n"
            f"📊 Изменение: {'+' if amount > 0 else ''}{amount}\n"
            f"⭐️ Новая карма: {new_karma}"
        )
        
        # Send notification to chat
        emoji = "👍" if amount > 0 else "👎"
        action = "повысили" if amount > 0 else "понизили"
        
        try:
            await bot.send_message(
                chat_id,
                f"{emoji} <b>{action.capitalize()} рейтинг!</b>\n\n"
                f"Администратор изменил рейтинг пользователя <b>{target_user_name}</b>.\n"
                f"Теперь его рейтинг: <b>{new_karma}</b> ❤️"
            )
        except Exception as e:
            logger.error("failed_to_send_karma_notification", chat_id=chat_id, error=str(e))
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Отправьте число:")


@router.message(Command("removekarma"))
@router.message(F.text.lower() == "убавить карму")
async def cmd_remove_karma(message: Message, state: FSMContext):
    """Shortcut for removing karma."""
    await cmd_add_karma(message, state)
    await message.answer("💡 <i>Отправьте отрицательное число для уменьшения кармы</i>")
