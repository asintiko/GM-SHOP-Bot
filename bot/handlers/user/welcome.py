"""
Welcome message handler for new members.
"""

from aiogram import Router
from aiogram.types import ChatMemberUpdated, FSInputFile
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
import structlog
import os

from bot.database import models

logger = structlog.get_logger(__name__)
router = Router(name="welcome")

# Path to welcome photo
WELCOME_PHOTO_PATH = "/app/photo/welcome.JPEG"


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    """Handle new member joining the chat."""
    chat_id = event.chat.id
    user = event.new_chat_member.user

    # Skip bots
    if user.is_bot:
        return

    # Get or create user and chat member record
    await models.get_or_create_user(
        user.id,
        user.first_name,
        user.last_name,
        user.username,
        user.is_bot
    )
    await models.get_or_create_chat_member(chat_id, user.id)

    # Get chat settings
    settings = await models.get_chat_settings(chat_id)
    welcome_settings = settings.get("welcome", {})

    # Check if welcome is enabled
    if not welcome_settings.get("enabled", True):
        return

    # Get custom welcome text or use default
    welcome_text = welcome_settings.get("custom_text")

    if not welcome_text:
        # Default welcome from specification
        welcome_text = f"""<b>Приветствуем, <a href="tg://user?id={user.id}">{user.first_name}</a> 👋 в магазине «GM SHOP»!</b>

🛒 Здесь ты найдёшь <b>самый дешёвый донат</b> в игры и <b>лучший сервис</b> на рынке.
❓ По всем вопросам — сразу к администраторам <i>(первыми не пишем)</i>.
🎁 Желаем приятного отдыха и выгодных покупок!

📜 <b>Правила чата:</b> набери <code>/rules</code> — обязательно ознакомься.
💬 <b>Команды бота:</b> <code>/help</code> — посмотри все доступные команды.
🏷 <b>Прозвище:</b> <code>/setnick</code> — установи себе уникальное прозвище в чате."""
    else:
        # Format custom text with user data
        welcome_text = welcome_text.format(
            user_id=user.id,
            first_name=user.first_name,
            username=user.username or user.first_name
        )

    # Send welcome message with photo
    try:
        if os.path.exists(WELCOME_PHOTO_PATH):
            photo = FSInputFile(WELCOME_PHOTO_PATH)
            sent_message = await event.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=welcome_text
            )
        else:
            # Fallback to text if photo not found
            sent_message = await event.answer(welcome_text)
            logger.warning("welcome_photo_not_found", path=WELCOME_PHOTO_PATH)
    except Exception as e:
        logger.error("failed_to_send_welcome", error=str(e))
        # Fallback to text message
        sent_message = await event.answer(welcome_text)

    logger.info("welcome_sent", chat_id=chat_id, user_id=user.id)

    # Auto-delete if configured
    auto_delete_minutes = welcome_settings.get("auto_delete_minutes")
    if auto_delete_minutes and auto_delete_minutes > 0:
        # TODO: Schedule message deletion
        # This would be handled by APScheduler in a full implementation
        pass

    # TODO: Pin rules message if configured
    # pin_rules = welcome_settings.get("pin_rules", False)
