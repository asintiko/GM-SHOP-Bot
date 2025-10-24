"""
Nickname management commands.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import structlog

from bot.database import models

logger = structlog.get_logger(__name__)
router = Router(name="nickname")


@router.message(Command("setnick"))
@router.message(F.text.lower().startswith("!прозвище "))
async def cmd_set_nickname(message: Message):
    """Set user nickname."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Extract nickname from command
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            "📝 <b>Установка прозвища</b>\n\n"
            "Использование: <code>/setnick ваше_прозвище</code>\n"
            "или: <code>!прозвище ваше_прозвище</code>\n\n"
            "Прозвище должно быть от 2 до 32 символов.\n"
            "Можно использовать: буквы, цифры, _ и -\n\n"
            "Чтобы убрать прозвище: <code>/removenick</code>"
        )
        return

    nickname = args[1].strip()

    # Set nickname
    success, error = await models.set_nickname(chat_id, user_id, nickname)

    if success:
        await message.reply(
            f"✅ <b>Прозвище установлено!</b>\n\n"
            f"Теперь вы отображаетесь как: <b>{nickname}</b>\n"
            f"Это будет видно в профиле, карме и других командах."
        )
        logger.info("nickname_set_success", chat_id=chat_id, user_id=user_id, nickname=nickname)
    else:
        await message.reply(f"❌ {error}")
        logger.warning("nickname_set_failed", chat_id=chat_id, user_id=user_id, error=error)


@router.message(Command("removenick"))
@router.message(F.text.lower() == "!убратьпрозвище")
async def cmd_remove_nickname(message: Message):
    """Remove user nickname."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    await models.remove_nickname(chat_id, user_id)

    await message.reply(
        "✅ <b>Прозвище удалено!</b>\n\n"
        "Теперь вы снова отображаетесь по имени из профиля Telegram."
    )
    logger.info("nickname_removed_success", chat_id=chat_id, user_id=user_id)


@router.message(Command("mynick"))
@router.message(F.text.lower() == "!моепрозвище")
async def cmd_my_nickname(message: Message):
    """Show current nickname."""
    if message.chat.type == "private":
        await message.answer("ℹ️ Эта команда работает только в группе.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Get current nickname
    member = await models.get_or_create_chat_member(chat_id, user_id)
    nickname = member.get('nickname')

    if nickname:
        await message.reply(
            f"👤 <b>Ваше прозвище:</b> {nickname}\n\n"
            f"Чтобы изменить: <code>/setnick новое_прозвище</code>\n"
            f"Чтобы убрать: <code>/removenick</code>"
        )
    else:
        await message.reply(
            "ℹ️ <b>У вас нет прозвища</b>\n\n"
            f"Чтобы установить: <code>/setnick ваше_прозвище</code>"
        )
