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


@router.my_chat_member(ADMINISTRATOR >> (IS_NOT_MEMBER | KICKED))
async def bot_removed_from_channel(event: ChatMemberUpdated, db: Database):
    """
    Бот полностью потерял доступ к каналу (кикнут/канал покинут) — это ближе всего
    к сигналу «канала больше нет или им больше не управляем», поэтому чистим реестр
    автоматически. Учтите: при полном удалении канала владельцем Telegram не всегда
    присылает этот update — тогда почистить вручную можно кнопкой
    «🗑 Отключить канал» в карточке канала.
    """
    chat_id = event.chat.id
    ch = await db.get_channel(chat_id)
    if ch is None:
        return
    await db.delete_channel_cascade(chat_id)
    logger.info("Канал автоматически убран из реестра (бот потерял доступ): %s (%s)", ch["title"], chat_id)


@router.my_chat_member(ADMINISTRATOR >> IS_MEMBER)
async def bot_demoted_to_member(event: ChatMemberUpdated):
    """Бота разжаловали до обычного участника (права админа сняли, но из канала не выгнали)."""
    logger.warning(
        "Бот потерял права администратора в канале %s (%s) — заявки и рассылка "
        "работать не будут, пока права не вернут.",
        event.chat.title, event.chat.id,
    )
