import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from database import Database
from utils.flood_queue import FloodQueue

from handlers import (
    membership,
    join_request,
    user_callbacks,
    admin_menu,
    admin_channels,
    admin_welcome,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    config = load_config()
    if config.bot_token == "PUT_YOUR_TOKEN_HERE":
        raise RuntimeError("Задайте переменную окружения BOT_TOKEN перед запуском.")

    db = Database(config.db_path)
    await db.connect()

    flood_queue = FloodQueue(delay_seconds=config.flood_delay_seconds)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Пробрасываем общие зависимости во все хендлеры через middleware-data aiogram 3
    dp["db"] = db
    dp["config"] = config
    dp["flood_queue"] = flood_queue

    # Порядок важен: сначала членство/заявки/пользовательские колбэки,
    # затем админ-разделы.
    dp.include_router(membership.router)
    dp.include_router(join_request.router)
    dp.include_router(user_callbacks.router)
    dp.include_router(admin_menu.router)
    dp.include_router(admin_channels.router)
    dp.include_router(admin_welcome.router)

    logger.info("Бот запускается...")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
                "chat_join_request",
                "my_chat_member",
            ],
        )
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
