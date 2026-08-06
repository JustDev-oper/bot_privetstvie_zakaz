import aiosqlite
from datetime import datetime
from typing import Optional, Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER UNIQUE NOT NULL,
    title TEXT,
    invite_link TEXT,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS welcome_chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_channel_id INTEGER UNIQUE NOT NULL,
    lock_enabled INTEGER NOT NULL DEFAULT 0,
    reward_channel_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chain_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id INTEGER NOT NULL REFERENCES welcome_chains(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    content_type TEXT NOT NULL,     -- text/photo/video/video_note/voice/document/animation
    file_id TEXT,
    text TEXT,
    delay_seconds INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS lock_required_channels (
    chain_id INTEGER NOT NULL REFERENCES welcome_chains(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL,
    PRIMARY KEY (chain_id, channel_id)
);

CREATE TABLE IF NOT EXISTS join_requests (
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, channel_id)
);

CREATE TABLE IF NOT EXISTS pending_invite_links (
    user_id INTEGER NOT NULL,
    reward_channel_id INTEGER NOT NULL,
    invite_link TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, reward_channel_id)
);

CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    # ------------------------------------------------------------------ #
    #  Каналы
    # ------------------------------------------------------------------ #
    async def upsert_channel(self, chat_id: int, title: str) -> None:
        await self._conn.execute(
            """INSERT INTO channels (chat_id, title) VALUES (?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title""",
            (chat_id, title),
        )
        await self._conn.commit()

    async def delete_channel_cascade(self, chat_id: int) -> None:
        """
        Полностью убирает канал из сети: его собственную приветственную цепочку
        (шаги и условия замка удалятся каскадно по FK), упоминания этого канала
        как условия в чужих замках, ссылки на него как на канал-награду,
        историю заявок и отложенные одноразовые инвайты.
        """
        chain = await self.get_chain_by_source(chat_id)
        if chain:
            await self._conn.execute("DELETE FROM welcome_chains WHERE id=?", (chain["id"],))

        await self._conn.execute("DELETE FROM lock_required_channels WHERE channel_id=?", (chat_id,))

        await self._conn.execute(
            "UPDATE welcome_chains SET lock_enabled=0, reward_channel_id=NULL WHERE reward_channel_id=?",
            (chat_id,),
        )

        await self._conn.execute("DELETE FROM join_requests WHERE channel_id=?", (chat_id,))
        await self._conn.execute("DELETE FROM pending_invite_links WHERE reward_channel_id=?", (chat_id,))
        await self._conn.execute("DELETE FROM channels WHERE chat_id=?", (chat_id,))
        await self._conn.commit()

    async def remove_channel(self, chat_id: int) -> None:
        await self._conn.execute("DELETE FROM channels WHERE chat_id=?", (chat_id,))
        await self._conn.commit()

    async def set_channel_invite_link(self, chat_id: int, link: str) -> None:
        await self._conn.execute(
            "UPDATE channels SET invite_link=? WHERE chat_id=?", (link, chat_id)
        )
        await self._conn.commit()

    async def list_channels(self) -> list[aiosqlite.Row]:
        cur = await self._conn.execute("SELECT * FROM channels ORDER BY added_at")
        return await cur.fetchall()

    async def get_channel(self, chat_id: int) -> Optional[aiosqlite.Row]:
        cur = await self._conn.execute("SELECT * FROM channels WHERE chat_id=?", (chat_id,))
        return await cur.fetchone()

    # ------------------------------------------------------------------ #
    #  Цепочки приветствий
    # ------------------------------------------------------------------ #
    async def get_chain_by_source(self, source_channel_id: int) -> Optional[aiosqlite.Row]:
        cur = await self._conn.execute(
            "SELECT * FROM welcome_chains WHERE source_channel_id=?", (source_channel_id,)
        )
        return await cur.fetchone()

    async def get_chain(self, chain_id: int) -> Optional[aiosqlite.Row]:
        cur = await self._conn.execute("SELECT * FROM welcome_chains WHERE id=?", (chain_id,))
        return await cur.fetchone()

    async def create_or_get_chain(self, source_channel_id: int) -> int:
        existing = await self.get_chain_by_source(source_channel_id)
        if existing:
            return existing["id"]
        cur = await self._conn.execute(
            "INSERT INTO welcome_chains (source_channel_id) VALUES (?)", (source_channel_id,)
        )
        await self._conn.commit()
        return cur.lastrowid

    async def clear_chain_steps(self, chain_id: int) -> None:
        await self._conn.execute("DELETE FROM chain_steps WHERE chain_id=?", (chain_id,))
        await self._conn.commit()

    async def add_chain_step(
        self,
        chain_id: int,
        step_order: int,
        content_type: str,
        file_id: Optional[str],
        text: Optional[str],
        delay_seconds: int,
    ) -> None:
        await self._conn.execute(
            """INSERT INTO chain_steps (chain_id, step_order, content_type, file_id, text, delay_seconds)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chain_id, step_order, content_type, file_id, text, delay_seconds),
        )
        await self._conn.commit()

    async def get_chain_steps(self, chain_id: int) -> list[aiosqlite.Row]:
        cur = await self._conn.execute(
            "SELECT * FROM chain_steps WHERE chain_id=? ORDER BY step_order", (chain_id,)
        )
        return await cur.fetchall()

    async def delete_chain_step(self, step_id: int) -> None:
        """Удаляет шаг по id и переупорядочивает оставшиеся шаги цепочки."""
        # Определяем chain_id и step_order удаляемого шага
        cur = await self._conn.execute(
            "SELECT chain_id, step_order FROM chain_steps WHERE id=?", (step_id,)
        )
        row = await cur.fetchone()
        if not row:
            return
        chain_id = row["chain_id"]
        deleted_order = row["step_order"]

        await self._conn.execute("DELETE FROM chain_steps WHERE id=?", (step_id,))

        # Сдвигаем step_order всех последующих шагов на -1
        await self._conn.execute(
            "UPDATE chain_steps SET step_order = step_order - 1 "
            "WHERE chain_id=? AND step_order > ?",
            (chain_id, deleted_order),
        )
        await self._conn.commit()

    async def set_chain_active(self, chain_id: int, active: bool) -> None:
        await self._conn.execute(
            "UPDATE welcome_chains SET is_active=? WHERE id=?", (int(active), chain_id)
        )
        await self._conn.commit()

    async def set_lock(
        self, chain_id: int, enabled: bool, reward_channel_id: Optional[int]
    ) -> None:
        await self._conn.execute(
            "UPDATE welcome_chains SET lock_enabled=?, reward_channel_id=? WHERE id=?",
            (int(enabled), reward_channel_id, chain_id),
        )
        await self._conn.commit()

    async def set_lock_required_channels(self, chain_id: int, channel_ids: list[int]) -> None:
        await self._conn.execute(
            "DELETE FROM lock_required_channels WHERE chain_id=?", (chain_id,)
        )
        await self._conn.executemany(
            "INSERT INTO lock_required_channels (chain_id, channel_id) VALUES (?, ?)",
            [(chain_id, cid) for cid in channel_ids],
        )
        await self._conn.commit()

    async def get_lock_required_channels(self, chain_id: int) -> list[int]:
        cur = await self._conn.execute(
            "SELECT channel_id FROM lock_required_channels WHERE chain_id=?", (chain_id,)
        )
        rows = await cur.fetchall()
        return [r["channel_id"] for r in rows]

    async def list_chains_with_channel_titles(self) -> list[aiosqlite.Row]:
        cur = await self._conn.execute(
            """SELECT wc.*, c.title AS source_title
               FROM welcome_chains wc
               JOIN channels c ON c.chat_id = wc.source_channel_id
               ORDER BY wc.created_at"""
        )
        return await cur.fetchall()

    # ------------------------------------------------------------------ #
    #  Заявки пользователей
    # ------------------------------------------------------------------ #
    async def add_join_request(self, user_id: int, channel_id: int) -> None:
        await self._conn.execute(
            """INSERT OR IGNORE INTO join_requests (user_id, channel_id) VALUES (?, ?)""",
            (user_id, channel_id),
        )
        await self._conn.commit()

    async def user_has_request(self, user_id: int, channel_id: int) -> bool:
        cur = await self._conn.execute(
            "SELECT 1 FROM join_requests WHERE user_id=? AND channel_id=?",
            (user_id, channel_id),
        )
        return (await cur.fetchone()) is not None

    async def get_missing_channels(self, user_id: int, required_channel_ids: list[int]) -> list[int]:
        missing = []
        for cid in required_channel_ids:
            if not await self.user_has_request(user_id, cid):
                missing.append(cid)
        return missing

    # ------------------------------------------------------------------ #
    #  Разовые пригласительные ссылки в канал-награду
    # ------------------------------------------------------------------ #
    async def save_pending_invite(self, user_id: int, reward_channel_id: int, link: str) -> None:
        await self._conn.execute(
            """INSERT OR REPLACE INTO pending_invite_links
               (user_id, reward_channel_id, invite_link) VALUES (?, ?, ?)""",
            (user_id, reward_channel_id, link),
        )
        await self._conn.commit()

    async def pop_pending_invite(self, user_id: int, reward_channel_id: int) -> Optional[str]:
        cur = await self._conn.execute(
            """SELECT invite_link FROM pending_invite_links
               WHERE user_id=? AND reward_channel_id=?""",
            (user_id, reward_channel_id),
        )
        row = await cur.fetchone()
        if row:
            await self._conn.execute(
                "DELETE FROM pending_invite_links WHERE user_id=? AND reward_channel_id=?",
                (user_id, reward_channel_id),
            )
            await self._conn.commit()
            return row["invite_link"]
        return None

    # ------------------------------------------------------------------ #
    #  Админы (доп. к тем, что заданы в конфиге)
    # ------------------------------------------------------------------ #
    async def add_admin(self, user_id: int) -> None:
        await self._conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await self._conn.commit()

    async def list_admin_ids(self) -> list[int]:
        cur = await self._conn.execute("SELECT user_id FROM admins")
        rows = await cur.fetchall()
        return [r["user_id"] for r in rows]
