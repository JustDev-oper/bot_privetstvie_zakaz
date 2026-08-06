from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import Config
from database import Database
import keyboards as kb
from handlers.admin_common import is_admin

router = Router(name="admin_menu")


@router.message(Command("admin"))
async def admin_entry(message: Message, config: Config, db: Database):
    if not await is_admin(message.from_user.id, config, db):
        await message.answer("⛔️ Эта команда доступна только администраторам бота.")
        return
    await message.answer(
        "🛠 <b>Панель управления сетью каналов</b>",
        parse_mode="HTML",
        reply_markup=kb.admin_main_menu(),
    )


@router.callback_query(F.data == "adm:menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 <b>Панель управления сетью каналов</b>", parse_mode="HTML",
                                  reply_markup=kb.admin_main_menu())
    await call.answer()


@router.callback_query(F.data == "adm:help")
async def help_screen(call: CallbackQuery):
    text = (
        "ℹ️ <b>Как это работает</b>\n\n"
        "1️⃣ Добавьте бота админом во все каналы сети (права: обработка заявок + инвайт-ссылки).\n"
        "2️⃣ Каналы появятся в разделе «📡 Каналы сети» автоматически, как только бот получит права.\n"
        "3️⃣ Для каждого канала создайте реф-ссылку (кнопка 🔗) и настройте приветственную цепочку (✉️).\n"
        "4️⃣ При желании включите 🔒 «Замок-доступ»: пользователь получит ссылку на закрытый "
        "канал-награду только после подачи заявок во все выбранные каналы."
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.back_to_menu())
    await call.answer()
