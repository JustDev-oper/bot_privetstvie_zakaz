import os
from dataclasses import dataclass, field


@dataclass
class Config:
    bot_token: str
    db_path: str = "./data/bot.db"
    admin_ids: list[int] = field(default_factory=list)
    # сколько ждать перед отправкой "неприоритетного" приветствия,
    # если пользователь почти одновременно подал заявки в несколько каналов сети
    flood_delay_seconds: int = 150  # 2.5 минуты (внутри диапазона 2–3 мин из ТЗ)


def load_config() -> Config:
    """
    Токен и список админов берём из переменных окружения, чтобы не хранить
    секреты в коде:

        export BOT_TOKEN="123456:AA...."
        export ADMIN_IDS="111111111,222222222"
    """
    token = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
    admins_raw = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(x) for x in admins_raw.split(",") if x.strip().isdigit()]
    db_path = os.getenv("BOT_DB_PATH", "./data/bot.db")
    return Config(bot_token=token, admin_ids=admin_ids, db_path=db_path)
