from config import Config
from database import Database


async def is_admin(user_id: int, config: Config, db: Database) -> bool:
    if user_id in config.admin_ids:
        return True
    db_admins = await db.list_admin_ids()
    return user_id in db_admins
