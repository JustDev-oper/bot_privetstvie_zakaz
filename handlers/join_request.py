import logging
from aiogram import Router, Bot
from aiogram.types import ChatJoinRequest

from database import Database
from utils.flood_queue import FloodQueue
from utils.chain_sender import send_welcome_chain

logger = logging.getLogger(__name__)
router = Router(name="join_request")


@router.chat_join_request()
async def on_join_request(event: ChatJoinRequest, db: Database, bot: Bot, flood_queue: FloodQueue):
    user_id = event.from_user.id
    channel_id = event.chat.id

    # Фиксируем заявку — она нужна и для проверки условий "замка",
    # и как источник данных для user_chat_id (позволяет писать юзеру напрямую).
    await db.add_join_request(user_id, channel_id)

    # 1) Канал является "наградой" какой-то цепочки?
    #    -> одобряем заявку автоматически и гасим одноразовую ссылку.
    reward_link = await db.pop_pending_invite(user_id, channel_id)
    if reward_link is not None:
        try:
            await bot.approve_chat_join_request(chat_id=channel_id, user_id=user_id)
        except Exception:
            logger.exception("Не удалось одобрить заявку user_id=%s в канал-награду %s", user_id, channel_id)
        try:
            await bot.revoke_chat_invite_link(chat_id=channel_id, invite_link=reward_link)
        except Exception:
            logger.exception("Не удалось отозвать одноразовую ссылку %s", reward_link)
        return  # это была заявка в канал-награду, приветственную цепочку сюда не шлём

    # 2) Канал является "источником" — у него настроена приветственная цепочка?
    chain = await db.get_chain_by_source(channel_id)
    if not chain or not chain["is_active"]:
        return

    # event.chat_join_request содержит user_chat_id (Bot API 6.5+), что позволяет
    # написать пользователю в личные сообщения без предварительного /start у бота.
    target_id = event.user_chat_id or user_id

    async def _send():
        await send_welcome_chain(bot, db, target_id, chain)

    # Анти-флуд: если у юзера уже "летит" мгновенное сообщение по другому каналу
    # сети — это сообщение уйдёт с задержкой 2-3 минуты.
    await flood_queue.dispatch(user_id, _send)
