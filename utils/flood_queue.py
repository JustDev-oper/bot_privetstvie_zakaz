import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class FloodQueue:
    """
    Защита от спам-бана Telegram.

    Если пользователь почти одновременно подаёт заявки в несколько каналов
    сети (например, кликает подряд по нескольким кнопкам-приглашениям),
    первое приветствие уходит сразу, а последующие ставятся в очередь
    с задержкой, чтобы бот не рассылал пачку сообщений одному человеку
    за секунды (это триггерит анти-спам системы Telegram).
    """

    def __init__(self, delay_seconds: int = 150):
        self.delay_seconds = delay_seconds
        self._sent_immediately: set[int] = set()  # user_id, кому уже ушло "мгновенное" сообщение
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def dispatch(self, user_id: int, send_coro_factory: Callable[[], Awaitable[None]]) -> None:
        """
        send_coro_factory — функция без аргументов, возвращающая корутину отправки.
        Передаём фабрику (а не саму корутину), т.к. корутину нельзя запустить дважды,
        а нам может понадобиться отложенный запуск через create_task.
        """
        async with self._locks[user_id]:
            is_first = user_id not in self._sent_immediately
            if is_first:
                self._sent_immediately.add(user_id)

        if is_first:
            try:
                await send_coro_factory()
            except Exception:
                logger.exception("Не удалось отправить мгновенное приветствие user_id=%s", user_id)
        else:
            asyncio.create_task(self._delayed_send(user_id, send_coro_factory))

    async def _delayed_send(self, user_id: int, send_coro_factory: Callable[[], Awaitable[None]]) -> None:
        await asyncio.sleep(self.delay_seconds)
        try:
            await send_coro_factory()
        except Exception:
            logger.exception("Не удалось отправить отложенное приветствие user_id=%s", user_id)
