from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database import Database
import keyboards as kb
from states import ChainBuilder

router = Router(name="admin_welcome")


def _extract_content(message: Message):
    """Достаёт тип контента, file_id и HTML-текст/подпись из сообщения админа."""
    if message.text is not None:
        return "text", None, message.html_text
    if message.photo:
        return "photo", message.photo[-1].file_id, message.html_text
    if message.video:
        return "video", message.video.file_id, message.html_text
    if message.video_note:
        return "video_note", message.video_note.file_id, None  # кружочки без подписи
    if message.voice:
        return "voice", message.voice.file_id, message.html_text
    if message.document:
        return "document", message.document.file_id, message.html_text
    if message.animation:
        return "animation", message.animation.file_id, message.html_text
    return None, None, None


# ---------------------------------------------------------------------- #
#  Вход в конструктор
# ---------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("adm:chain_edit:"))
async def open_chain_builder(call: CallbackQuery, db: Database, state: FSMContext):
    chat_id = int(call.data.split(":")[2])
    ch = await db.get_channel(chat_id)
    if not ch:
        await call.answer("Канал не найден", show_alert=True)
        return

    chain_id = await db.create_or_get_chain(chat_id)
    steps = await db.get_chain_steps(chain_id)

    await state.set_data({
        "chat_id": chat_id,
        "chain_id": chain_id,
        "next_order": len(steps),
        "selected_lock": set(),
    })
    await state.set_state(None)

    text = (
        f"✉️ <b>Приветственная цепочка</b> для «{ch['title']}»\n\n"
        f"Сейчас в цепочке сообщений: <b>{len(steps)}</b> 📨\n\n"
        "Добавляйте посты по очереди — форматирование, фото/видео/кружочки/голосовые "
        "сохранятся 1-в-1 ✨"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.chain_builder_menu(bool(steps)))
    await call.answer()


# ---------------------------------------------------------------------- #
#  Добавление шага
# ---------------------------------------------------------------------- #
@router.callback_query(F.data == "chain:add_step")
async def ask_step_content(call: CallbackQuery, state: FSMContext):
    await state.set_state(ChainBuilder.waiting_step_content)
    await call.message.edit_text(
        "📝 Пришлите следующее сообщение цепочки: текст, фото, видео, кружочек, "
        "голосовое или документ (одним сообщением).",
    )
    await call.answer()


@router.message(ChainBuilder.waiting_step_content)
async def receive_step_content(message: Message, state: FSMContext):
    content_type, file_id, text = _extract_content(message)
    if content_type is None:
        await message.answer("⚠️ Такой тип контента пока не поддерживается, пришлите текст, фото, видео, кружочек, голосовое или документ.")
        return

    await state.update_data(pending_step={"content_type": content_type, "file_id": file_id, "text": text})
    await state.set_state(ChainBuilder.waiting_step_delay)
    await message.answer(
        "⏱ Через сколько отправить это сообщение после предыдущего в цепочке?",
        reply_markup=kb.ask_delay_menu(),
    )


@router.callback_query(ChainBuilder.waiting_step_delay, F.data.startswith("delay:"))
async def receive_step_delay(call: CallbackQuery, db: Database, state: FSMContext):
    delay_seconds = int(call.data.split(":")[1])
    data = await state.get_data()
    pending = data["pending_step"]

    await db.add_chain_step(
        chain_id=data["chain_id"],
        step_order=data["next_order"],
        content_type=pending["content_type"],
        file_id=pending["file_id"],
        text=pending["text"],
        delay_seconds=delay_seconds,
    )
    await state.update_data(next_order=data["next_order"] + 1, pending_step=None)
    await state.set_state(None)

    steps = await db.get_chain_steps(data["chain_id"])
    await call.message.edit_text(
        f"✅ Добавлено! В цепочке сейчас {len(steps)} сообщений 📨\n\nЧто дальше?",
        reply_markup=kb.chain_builder_menu(True),
    )
    await call.answer()


# ---------------------------------------------------------------------- #
#  Сохранение без замка
# ---------------------------------------------------------------------- #
@router.callback_query(F.data == "chain:save")
async def save_chain_no_lock_prompt(call: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    await db.set_chain_active(data["chain_id"], True)
    await state.clear()
    await call.message.edit_text(
        "✅ Приветственная цепочка сохранена и включена! 🎉\n\n"
        "Теперь она будет отправляться каждому, кто подаёт заявку в этот канал.",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


# ---------------------------------------------------------------------- #
#  Модуль «Замок-доступ»
# ---------------------------------------------------------------------- #
@router.callback_query(F.data == "chain:lock_setup")
async def lock_setup_start(call: CallbackQuery, db: Database, state: FSMContext):
    await state.update_data(selected_lock=set())
    await state.set_state(ChainBuilder.lock_select_required)
    channels = await db.list_channels()
    await call.message.edit_text(
        "🔒 <b>Обязательная подписка</b>\n\n"
        "Отметьте каналы, в которые пользователь должен подать заявки, "
        "чтобы получить доступ к каналу-награде:",
        parse_mode="HTML",
        reply_markup=kb.lock_toggle_menu(channels, set()),
    )
    await call.answer()


@router.callback_query(ChainBuilder.lock_select_required, F.data.startswith("lock:toggle:"))
async def lock_toggle_channel(call: CallbackQuery, db: Database, state: FSMContext):
    cid = int(call.data.split(":")[2])
    data = await state.get_data()
    selected: set = data.get("selected_lock", set())
    if cid in selected:
        selected.discard(cid)
    else:
        selected.add(cid)
    await state.update_data(selected_lock=selected)

    channels = await db.list_channels()
    await call.message.edit_reply_markup(reply_markup=kb.lock_toggle_menu(channels, selected))
    await call.answer()


@router.callback_query(ChainBuilder.lock_select_required, F.data == "lock:next_reward")
async def lock_go_to_reward(call: CallbackQuery, db: Database, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_lock"):
        await call.answer("Выберите хотя бы один канал ⚠️", show_alert=True)
        return
    await state.set_state(ChainBuilder.lock_select_reward)
    channels = await db.list_channels()
    await call.message.edit_text(
        "🏆 Выберите канал-<b>награду</b> — доступ к нему пользователь получит "
        "после выполнения условий:",
        parse_mode="HTML",
        reply_markup=kb.lock_reward_menu(channels),
    )
    await call.answer()


@router.callback_query(ChainBuilder.lock_select_reward, F.data.startswith("lock:reward:"))
async def lock_finish_with_reward(call: CallbackQuery, db: Database, state: FSMContext):
    reward_id = int(call.data.split(":")[2])
    data = await state.get_data()
    await db.set_lock(data["chain_id"], True, reward_id)
    await db.set_lock_required_channels(data["chain_id"], list(data["selected_lock"]))
    await db.set_chain_active(data["chain_id"], True)
    await state.clear()
    await call.message.edit_text(
        "✅ Замок-доступ настроен и цепочка включена! 🔒🎉",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


@router.callback_query(ChainBuilder.lock_select_reward, F.data == "lock:disable")
async def lock_disable(call: CallbackQuery, db: Database, state: FSMContext):
    data = await state.get_data()
    await db.set_lock(data["chain_id"], False, None)
    await db.set_chain_active(data["chain_id"], True)
    await state.clear()
    await call.message.edit_text(
        "✅ Цепочка сохранена и включена (без замка-доступа).",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()
