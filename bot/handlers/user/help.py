"""
Help command handler with role-based content.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
import structlog
import os

from bot.database import models

logger = structlog.get_logger(__name__)
router = Router(name="help")

# Path to help photo
HELP_PHOTO_PATH = "/app/photo/help.JPEG"


@router.message(Command("help"))
@router.message(F.text.lower().in_(["!команды", "!help"]))
async def cmd_help(message: Message):
    """Show available commands based on user role."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    is_private = message.chat.type == "private"

    # Get user role (for group chats)
    role = None if is_private else await models.get_user_role(chat_id, user_id)

    # Build help text based on role and chat type
    help_text = "<b>📋 ДОСТУПНЫЕ КОМАНДЫ</b>\n\n"

    # User commands (available to everyone)
    help_text += "<b>👤 Команды пользователей:</b>\n"
    help_text += "• <code>/rules</code> — правила чата\n"
    help_text += "• <code>/karma</code> — показать карму\n"
    help_text += "• <code>/profile</code> — твой профиль\n"
    help_text += "• <code>/top</code> — топ недели\n"
    help_text += "• <code>!стата</code> — подробная статистика\n"
    help_text += "• <code>!общстат</code> — статистика чата\n"
    help_text += "• <code>/help</code> — эта справка\n\n"

    help_text += "<b>🏷 Прозвища:</b>\n"
    help_text += "• <code>/setnick</code> — установить прозвище\n"
    help_text += "• <code>/removenick</code> — удалить прозвище\n"
    help_text += "• <code>/mynick</code> — посмотреть прозвище\n\n"

    help_text += "<b>⭐ Карма через реакции:</b>\n"
    help_text += "👍❤️🔥 = +1 | 👎💩 = -1"

    # If user is staff, send detailed commands in PM
    if role in ["moderator", "admin", "owner"]:
        staff_text = "\n\n<b>👮 Модерация:</b>\n"
        staff_text += "• <code>/ban /mute /warn /kick</code>\n"
        staff_text += "• <code>/unban /unmute /unwarn</code>\n\n"

        if role in ["admin", "owner"]:
            staff_text += "<b>⚙️ Администрирование:</b>\n"
            staff_text += "• <code>/pin /unpin</code>\n"
            staff_text += "• <code>/addmod /delmod</code>\n"
            staff_text += "• <code>/settings</code> — настройки\n\n"

        if role == "owner":
            staff_text += "<b>👑 Владелец:</b>\n"
            staff_text += "• <code>/addadmin /deladmin</code>\n"
            staff_text += "• <code>/giveaway</code> — розыгрыш\n\n"

        # Send detailed commands to PM
        try:
            await message.bot.send_message(
                user_id,
                f"<b>📋 КОМАНДЫ МОДЕРАТОРА/АДМИНА</b>\n{staff_text}"
                f"💡 <i>Для модерации отвечайте на сообщение нарушителя командой</i>"
            )
            help_text += "\n\n✉️ <i>Команды модератора отправлены в ЛС</i>"
        except Exception as e:
            logger.warning("failed_to_send_pm", user_id=user_id, error=str(e))

    # Send help with photo
    try:
        if os.path.exists(HELP_PHOTO_PATH):
            photo = FSInputFile(HELP_PHOTO_PATH)
            await message.answer_photo(photo=photo, caption=help_text)
        else:
            await message.answer(help_text)
            logger.warning("help_photo_not_found", path=HELP_PHOTO_PATH)
    except Exception as e:
        logger.error("failed_to_send_help", error=str(e))
        await message.answer(help_text)

    logger.info("help_shown", chat_id=chat_id, user_id=user_id, role=role or "user")
