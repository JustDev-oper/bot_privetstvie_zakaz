import logging
from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ADMINISTRATOR, KICKED

from database import Database

logger = logging.getLogger(__name__)
router = Router(name="membership")


@router.my_chat_member(IS_NOT_MEMBER >> ADMINISTRATOR)
async def bot_promoted_to_admin(event: ChatMemberUpdated, db: Database, bot: Bot):
    """
    Как только бота делают админом канала — канал автоматически попадает
    в реестр (шаг перед добавлением реф-ссылки, п.2.1 ТЗ).
    """
    chat = event.chat
    await db.upsert_channel(chat_id=chat.id, title=chat.title or str(chat.id))
    logger.info("Канал добавлен в реестр: %s (%s)", chat.title, chat.id)


@router.my_chat_member(ADMINISTRATOR >> (IS_MEMBER | IS_NOT_MEMBER | KICKED))
async def bot_demoted(event: ChatMemberUpdated, db: Database):
    """Если бота разжаловали/удалили из канала — можно почистить реестр вручную из /admin."""
    logger.info("Бот потерял права администратора в канале %s (%s)", event.chat.title, event.chat.id)
