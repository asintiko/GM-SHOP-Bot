"""
Admin panel - settings management via private messages.
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberOwner, ChatMemberAdministrator
import structlog

from bot.config import settings
from bot.database import models
from bot.utils.deep_link import validate_settings_signature

logger = structlog.get_logger(__name__)
router = Router(name="admin_panel")


def is_owner(user_id: int) -> bool:
    """Check if user is owner."""
    return user_id in settings.owner_ids


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard."""
    buttons = [
        [InlineKeyboardButton(text="🛠 Настройки чата", callback_data="settings_main")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="settings_rules")],
        [InlineKeyboardButton(text="👋 Приветствие", callback_data="settings_welcome")],
        [InlineKeyboardButton(text="🧹 Антифлуд", callback_data="settings_antiflood")],
        [InlineKeyboardButton(text="🚫 Фильтры", callback_data="settings_filters")],
        [InlineKeyboardButton(text="❤️ Карма", callback_data="settings_karma")],
        [InlineKeyboardButton(text="🏆 Топ недели", callback_data="settings_weekly_top")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_chat_menu_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Get menu keyboard for specific chat settings."""
    buttons = [
        [InlineKeyboardButton(text="📜 Правила", callback_data=f"chat_{chat_id}_rules")],
        [InlineKeyboardButton(text="👋 Приветствие", callback_data=f"chat_{chat_id}_welcome")],
        [InlineKeyboardButton(text="🧹 Антифлуд", callback_data=f"chat_{chat_id}_antiflood")],
        [InlineKeyboardButton(text="🚫 Фильтры", callback_data=f"chat_{chat_id}_filters")],
        [InlineKeyboardButton(text="❤️ Карма", callback_data=f"chat_{chat_id}_karma")],
        [InlineKeyboardButton(text="🏆 Топ недели", callback_data=f"chat_{chat_id}_weekly_top")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, bot: Bot):
    """Start command in private chat."""
    user_id = message.from_user.id

    # Check for deep-link payload
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []

    if args and args[0].startswith("cfg_"):
        # Parse deep-link: cfg_<chat_id>_<signature>
        try:
            parts = args[0].split("_")
            if len(parts) != 3:
                raise ValueError("Invalid payload format")

            chat_id = int(parts[1])
            signature = parts[2]

            # Validate signature
            if not validate_settings_signature(chat_id, signature):
                await message.answer(
                    "❌ <b>Ошибка безопасности</b>\n\n"
                    "Недействительная подпись. Попробуйте создать новую ссылку из настроек чата."
                )
                logger.warning("invalid_signature", user_id=user_id, chat_id=chat_id)
                return

            # Check user permissions in that chat
            try:
                chat_member = await bot.get_chat_member(chat_id, user_id)
                if not isinstance(chat_member, (ChatMemberOwner, ChatMemberAdministrator)):
                    await message.answer(
                        "❌ <b>Недостаточно прав</b>\n\n"
                        "У вас нет прав администратора в этом чате."
                    )
                    logger.warning("insufficient_rights", user_id=user_id, chat_id=chat_id)
                    return
            except Exception as e:
                await message.answer(
                    "❌ <b>Ошибка</b>\n\n"
                    "Не удалось проверить ваши права в чате. Убедитесь, что вы являетесь участником чата."
                )
                logger.error("check_rights_failed", user_id=user_id, chat_id=chat_id, error=str(e))
                return

            # Get chat info
            try:
                chat = await bot.get_chat(chat_id)
                chat_title = chat.title
            except Exception:
                chat_title = f"Чат {chat_id}"

            # Open settings panel for this chat
            await message.answer(
                f"⚙️ <b>Настройки чата «{chat_title}»</b>\n\n"
                "Выберите раздел для настройки:",
                reply_markup=get_chat_menu_keyboard(chat_id)
            )

            logger.info("settings_opened_via_deeplink", user_id=user_id, chat_id=chat_id)
            return

        except (ValueError, IndexError) as e:
            await message.answer(
                "❌ <b>Ошибка</b>\n\n"
                "Неверный формат ссылки."
            )
            logger.error("invalid_deeplink_format", user_id=user_id, error=str(e))
            return

    # Regular start command
    if not is_owner(user_id):
        await message.answer(
            "👋 Привет! Я бот магазина GM SHOP.\n\n"
            "Добавь меня в свою группу и сделай администратором, "
            "чтобы я мог модерировать чат и проводить конкурсы!"
        )
        return

    await message.answer(
        "👋 <b>Привет, владелец!</b>\n\n"
        "Добро пожаловать в панель управления GM SHOP Bot.\n"
        "Используй кнопки ниже для настройки бота:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("menu"), F.chat.type == "private")
async def cmd_menu(message: Message):
    """Show main menu."""
    if not is_owner(message.from_user.id):
        return

    await message.answer(
        "🛠 <b>Панель управления</b>\n\n"
        "Выберите раздел для настройки:",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "menu")
async def callback_menu(callback: CallbackQuery):
    """Return to main menu."""
    if not is_owner(callback.from_user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "🛠 <b>Панель управления</b>\n\n"
        "Выберите раздел для настройки:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Show help."""
    help_text = """📚 <b>Справка по боту</b>

<b>Основные команды:</b>

<b>Для пользователей:</b>
/rules - Показать правила
/karma - Посмотреть карму
/profile - Показать профиль
/top - Показать топ недели

<b>Для модераторов:</b>
/ban @user [время] [причина]
/mute @user &lt;время&gt; [причина]
/warn @user [причина]
/kick @user [причина]

Также поддерживаются команды с !:
!бан, !мут, !варн, !кик

<b>Формат времени:</b>
50м, 3ч, 2д, 1w, 1h30m

<b>Возможности:</b>
• Автомодерация (антифлуд, фильтры)
• Система кармы
• Еженедельные топы с призами
• Конкурсы и розыгрыши"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(help_text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data == "settings_antiflood")
async def callback_antiflood_settings(callback: CallbackQuery):
    """Show antiflood settings."""
    # TODO: Load actual settings from database
    # For now, show current default settings

    text = """🧹 <b>Настройки антифлуда</b>

<b>Текущие настройки:</b>
• Включено: ✅
• Порог сообщений: 6 подряд
• Окно времени: 3 минуты
• Длительность мута: 50 минут
• Удалять сообщения: ✅

<i>Редактор настроек будет добавлен в следующей версии.</i>"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data == "settings_karma")
async def callback_karma_settings(callback: CallbackQuery):
    """Show karma settings."""
    text = """❤️ <b>Настройки кармы</b>

<b>Текущие настройки:</b>
• Включено: ✅
• Кулдаун: 12 часов
• Дневной лимит негатива: -3
• Вес в топе: ×2

<b>Позитивные триггеры:</b>
+, спасибо, спс, thx, благодарю

<b>Негативные триггеры:</b>
-, фу, кринж, дизлайк

<i>Редактор настроек будет добавлен в следующей версии.</i>"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data == "settings_weekly_top")
async def callback_weekly_top_settings(callback: CallbackQuery):
    """Show weekly top settings."""
    text = """🏆 <b>Настройки топа недели</b>

<b>Текущие настройки:</b>
• Включено: ✅
• День публикации: Понедельник
• Время: 12:00 МСК
• Количество мест: 3

<b>Формула расчёта:</b>
• Сообщения: ×1
• Карма: ×2
• Ответы: ×0.5
• Реакции: ×0.3

<b>Призы:</b>
1) 🥇 Донат на 500 руб
2) 🥈 Донат на 300 руб
3) 🥉 Донат на 200 руб

<i>Редактор настроек будет добавлен в следующей версии.</i>"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data == "settings_filters")
async def callback_filters_settings(callback: CallbackQuery):
    """Show content filters settings."""
    text = """🚫 <b>Настройки фильтров</b>

<b>Текущие настройки:</b>
• Включено: ✅
• Действие: Мут навсегда
• Проверка ссылок: ✅

<b>Фильтры спама:</b>
• Заработок/доход
• Ставки/казино
• 1win, mostbet, melbet
• Криптосигналы

<b>Белый список доменов:</b>
• t.me
• telegram.me

<i>Редактор фильтров будет добавлен в следующей версии.</i>"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data == "settings_rules")
async def callback_rules_settings(callback: CallbackQuery):
    """Show rules settings."""
    text = """📜 <b>Настройки правил</b>

Здесь вы можете настроить текст правил чата.

<i>Редактор правил будет добавлен в следующей версии.
Сейчас используется текст по умолчанию из спецификации.</i>"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()


@router.callback_query(F.data == "settings_welcome")
async def callback_welcome_settings(callback: CallbackQuery):
    """Show welcome settings."""
    text = """👋 <b>Настройки приветствия</b>

<b>Текущие настройки:</b>
• Включено: ✅
• Автоудаление: через 5 минут
• Закреплять правила: ❌

<i>Редактор приветствия будет добавлен в следующей версии.
Сейчас используется текст по умолчанию из спецификации.</i>"""

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await callback.message.edit_text(text, reply_markup=back_button)
    await callback.answer()
