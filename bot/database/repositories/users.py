import aiosqlite

from bot.database.db import Database
from bot.database.models import User


class UserRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert(self, tg_id: int, full_name: str, username: str | None) -> None:
        """Register a user or refresh their profile; also clears the 'blocked' flag."""
        await self._db.execute(
            """
            INSERT INTO users (tg_id, full_name, username) VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                is_blocked = 0,
                last_seen_at = datetime('now')
            """,
            (tg_id, full_name, username),
        )

    async def ensure(self, tg_id: int, *, conn: aiosqlite.Connection) -> None:
        await self._db.execute("INSERT OR IGNORE INTO users (tg_id) VALUES (?)", (tg_id,), conn=conn)

    async def get(self, tg_id: int) -> User | None:
        row = await self._db.fetch_one("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        return User.from_row(row) if row else None

    async def set_contact(self, tg_id: int, name: str, phone: str) -> None:
        """Remember the last used name/phone to pre-fill the next booking."""
        await self._db.execute(
            "UPDATE users SET contact_name = ?, phone = ? WHERE tg_id = ?", (name, phone or None, tg_id)
        )

    async def mark_blocked(self, tg_id: int) -> None:
        await self._db.execute("UPDATE users SET is_blocked = 1 WHERE tg_id = ?", (tg_id,))

    async def broadcast_ids(self) -> list[int]:
        rows = await self._db.fetch_all("SELECT tg_id FROM users WHERE is_blocked = 0 ORDER BY tg_id")
        return [row["tg_id"] for row in rows]

    async def count(self) -> int:
        row = await self._db.fetch_one("SELECT COUNT(*) AS n FROM users")
        return int(row["n"]) if row else 0
