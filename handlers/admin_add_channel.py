import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import Config
from database import Database
import keyboards as kb
from states import AddChannel
from handlers.admin_common import is_admin

logger = logging.getLogger(__name__)
router = Router(name="admin_add_channel")


@router.callback_query(F.data == "adm:add_channel")
async def add_channel_menu(call: CallbackQuery, db: Database, config: Config, state: FSMContext):
    if not await is_admin(call.from_user.id, config, db):
        await call.answer("⛔️ Только для админов", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "➕ <b>Подключить канал вручную</b>\n\n"
        "Используйте, если бот уже добавлен в канал администратором, но канал "
        "не появился в списке автоматически.",
        parse_mode="HTML",
        reply_markup=kb.add_channel_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "adm:add_by_forward")
async def ask_forward(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.waiting_forward)
    await call.message.edit_text(
        "📨 Перешлите сюда любое сообщение (пост) из нужного канала.\n\n"
        "⚠️ Если в настройках канала включена «скрытая пересылка», у пересланного "
        "сообщения не будет видно канал-источник — в этом случае воспользуйтесь "
        "вариантом «🆔 Ввести ID канала».",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "adm:add_by_id")
async def ask_id(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.waiting_id)
    await call.message.edit_text(
        "🆔 Пришлите ID канала одним сообщением.\n\n"
        "Обычно он выглядит так: <code>-1001234567890</code>\n"
        "Узнать ID можно, переслав любой пост из канала специальному боту "
        "(например @userinfobot) или посмотрев его в веб-версии Telegram.",
        parse_mode="HTML",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


def _extract_forward_chat(message: Message):
    """
    Достаёт канал-источник пересланного сообщения.
    Поддерживает и новый Bot API 7.0+ (forward_origin), и старый формат
    (forward_from_chat) — в зависимости от версии клиента/сервера может
    прийти любой из них.
    """
    origin = getattr(message, "forward_origin", None)
    if origin is not None and getattr(origin, "chat", None) is not None:
        return origin.chat
    legacy = getattr(message, "forward_from_chat", None)
    if legacy is not None:
        return legacy
    return None


@router.message(AddChannel.waiting_forward)
async def receive_forward(message: Message, db: Database, bot: Bot, state: FSMContext):
    chat = _extract_forward_chat(message)
    if chat is None or chat.type != "channel":
        await message.answer(
            "⚠️ Не вижу канал-источник у этого сообщения.\n\n"
            "Убедитесь, что:\n"
            "• пересылаете именно пост из канала, а не пересланное кем-то сообщение;\n"
            "• в канале не включена «скрытая пересылка» (тогда источник не виден вообще).\n\n"
            "Если источник скрыт — воспользуйтесь вариантом «🆔 Ввести ID канала»."
        )
        return
    await _register_channel(message, chat.id, db, bot, state)


@router.message(AddChannel.waiting_id)
async def receive_id(message: Message, db: Database, bot: Bot, state: FSMContext):
    raw = (message.text or "").strip()
    try:
        chat_id = int(raw)
    except ValueError:
        await message.answer(
            "⚠️ ID должен быть числом, например <code>-1001234567890</code>. Пришлите ещё раз.",
            parse_mode="HTML",
        )
        return
    await _register_channel(message, chat_id, db, bot, state)


async def _register_channel(message: Message, chat_id: int, db: Database, bot: Bot, state: FSMContext):
    try:
        chat = await bot.get_chat(chat_id)
    except TelegramBadRequest:
        await message.answer(
            "⚠️ Не удалось получить канал по этому ID/сообщению.\n\n"
            "Проверьте, что:\n"
            "• ID указан верно (с <code>-100</code> в начале для каналов);\n"
            "• бот действительно добавлен в этот канал администратором.",
            parse_mode="HTML",
        )
        return
    except Exception:
        logger.exception("Ошибка get_chat для %s", chat_id)
        await message.answer("⚠️ Не удалось получить канал, попробуйте ещё раз позже.")
        return

    if chat.type != "channel":
        await message.answer("⚠️ Это не канал, а чат/группа другого типа. Подключать можно только каналы.")
        return

    warning = ""
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        if member.status not in ("administrator", "creator"):
            warning = (
                "\n\n⚠️ Бот пока <b>не администратор</b> этого канала — обработка заявок "
                "и рассылка приветствий работать не будут, пока не выдадите права "
                "(«Управление заявками» + «Приглашение по ссылке»)."
            )
    except Exception:
        warning = "\n\n⚠️ Не удалось проверить права бота в канале — на всякий случай перепроверьте их вручную."

    await db.upsert_channel(chat_id=chat.id, title=chat.title or str(chat.id))
    await state.clear()
    await message.answer(
        f"✅ Канал «{chat.title}» подключён к сети!{warning}\n\n"
        "Теперь можно создать реф-ссылку и настроить приветствие в разделе «📡 Каналы сети».",
        parse_mode="HTML",
        reply_markup=kb.back_to_menu(),
    )
