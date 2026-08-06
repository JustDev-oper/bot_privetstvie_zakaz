import logging
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery

from database import Database

logger = logging.getLogger(__name__)
router = Router(name="user_callbacks")


@router.callback_query(F.data == "user:check")
async def check_subscription(call: CallbackQuery, db: Database, bot: Bot):
    user_id = call.from_user.id

    # Ищем цепочку, к которой относится этот пост, по каналу-награде,
    # прописанному в клавиатуре сообщения не храним явно — поэтому просто
    # перебираем активные цепочки с замком и ищем ту, для которой ссылки
    # в этом сообщении совпадают. Для простоты и надёжности храним привязку
    # через reward_channel_id, который передаём в callback_data.
    await call.answer()  # быстрый ack, чтобы кнопка не "висела"

    chains = await db.list_chains_with_channel_titles()
    matching_chain = None
    for chain in chains:
        if not chain["lock_enabled"] or not chain["is_active"]:
            continue
        required_ids = await db.get_lock_required_channels(chain["id"])
        if not required_ids:
            continue
        missing = await db.get_missing_channels(user_id, required_ids)
        if not missing:
            matching_chain = chain
            break
        # запомним последнюю цепочку с частичным прогрессом на случай,
        # если ни одна не выполнена полностью
        matching_chain = matching_chain or chain

    if matching_chain is None:
        await call.message.answer("🤔 Не нашёл активных условий доступа для этого поста.")
        return

    required_ids = await db.get_lock_required_channels(matching_chain["id"])
    missing = await db.get_missing_channels(user_id, required_ids)

    if missing:
        lines = ["🔸 Вы ещё не подали заявку в:"]
        for cid in missing:
            ch = await db.get_channel(cid)
            title = ch["title"] if ch else str(cid)
            lines.append(f"  📢 {title}")
        lines.append("\nПодайте заявки во все каналы выше и нажмите проверку ещё раз ✅")
        await call.message.answer("\n".join(lines))
        return

    reward_channel_id = matching_chain["reward_channel_id"]
    reward_channel = await db.get_channel(reward_channel_id) if reward_channel_id else None
    if reward_channel is None:
        await call.message.answer("⚠️ Канал-награда не настроен, обратитесь к администратору.")
        return

    try:
        link_obj = await bot.create_chat_invite_link(
            chat_id=reward_channel_id,
            creates_join_request=True,  # заявка, а не мгновенное присоединение (п.3 ТЗ)
            name=f"reward-{user_id}",
        )
    except Exception:
        logger.exception("Не удалось создать инвайт-ссылку в канал-награду %s", reward_channel_id)
        await call.message.answer("⚠️ Не удалось выдать доступ, попробуйте позже.")
        return

    await db.save_pending_invite(user_id, reward_channel_id, link_obj.invite_link)

    import keyboards as kb
    await call.message.answer(
        f"🎉 Все условия выполнены!\nЗаберите доступ к каналу «{reward_channel['title']}»:",
        reply_markup=kb.user_get_link_button(link_obj.invite_link),
    )
