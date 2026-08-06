import asyncio
import logging
from aiogram import Bot

from database import Database
import keyboards as kb

logger = logging.getLogger(__name__)

# Универсальные send_* методы aiogram по типу контента шага цепочки.
# Все они поддерживают parse_mode="HTML", а caption/text уже приходят
# из БД в исходном виде (мы сохраняем html_text из update, поэтому
# форматирование, встроенные ссылки и подписи сохраняются 1-в-1).
_SEND_MAP = {
    "text": "send_message",
    "photo": "send_photo",
    "video": "send_video",
    "video_note": "send_video_note",
    "voice": "send_voice",
    "document": "send_document",
    "animation": "send_animation",
}


async def send_welcome_chain(bot: Bot, db: Database, user_id: int, chain_row) -> None:
    """
    Отправляет пользователю всю цепочку приветственных постов по порядку,
    соблюдая заданные админом задержки между сообщениями.
    К последнему сообщению цепочки, если включён замок, прикрепляется
    клавиатура со ссылками на обязательные каналы + кнопка проверки.
    """
    steps = await db.get_chain_steps(chain_row["id"])
    if not steps:
        return

    required_ids: list[int] = []
    invite_links: dict[int, str] = {}
    if chain_row["lock_enabled"]:
        required_ids = await db.get_lock_required_channels(chain_row["id"])
        for cid in required_ids:
            ch = await db.get_channel(cid)
            if ch and ch["invite_link"]:
                invite_links[cid] = ch["invite_link"]

    last_index = len(steps) - 1

    for i, step in enumerate(steps):
        if step["delay_seconds"]:
            await asyncio.sleep(step["delay_seconds"])

        method_name = _SEND_MAP.get(step["content_type"], "send_message")
        method = getattr(bot, method_name)

        markup = None
        if i == last_index and chain_row["lock_enabled"] and required_ids:
            required_channels = [await db.get_channel(cid) for cid in required_ids]
            required_channels = [c for c in required_channels if c is not None]
            markup = kb.user_lock_keyboard(required_channels, invite_links)

        try:
            if step["content_type"] == "text":
                await method(user_id, text=step["text"], parse_mode="HTML", reply_markup=markup)
            else:
                await method(
                    user_id,
                    step["file_id"],
                    caption=step["text"],
                    parse_mode="HTML",
                    reply_markup=markup,
                )
        except Exception:
            logger.exception(
                "Ошибка отправки шага цепочки user_id=%s chain_id=%s step=%s",
                user_id, chain_row["id"], step["id"],
            )
            return
