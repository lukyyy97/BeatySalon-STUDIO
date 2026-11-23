import aiosqlite

from bot.database.db import Database
from bot.database.models import Master, Service


class CatalogRepo:
    """Services, masters and the master <-> service links."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ---- services ----
    async def list_services(
        self, *, active_only: bool = True, conn: aiosqlite.Connection | None = None
    ) -> list[Service]:
        sql = "SELECT * FROM services" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY id"
        return [Service.from_row(r) for r in await self._db.fetch_all(sql, conn=conn)]

    async def get_service(self, service_id: int, *, conn: aiosqlite.Connection | None = None) -> Service | None:
        row = await self._db.fetch_one("SELECT * FROM services WHERE id = ?", (service_id,), conn=conn)
        return Service.from_row(row) if row else None

    async def add_service(
        self, name: str, price: int, duration_min: int, *, conn: aiosqlite.Connection | None = None
    ) -> int:
        return await self._db.insert(
            "INSERT INTO services (name, price, duration_min) VALUES (?, ?, ?)",
            (name, price, duration_min),
            conn=conn,
        )

    async def update_service(
        self,
        service_id: int,
        *,
        name: str | None = None,
        price: int | None = None,
        duration_min: int | None = None,
        is_active: bool | None = None,
    ) -> None:
        await self._update(
            "services",
            service_id,
            {
                "name": name,
                "price": price,
                "duration_min": duration_min,
                "is_active": None if is_active is None else int(is_active),
            },
        )

    # ---- masters ----
    async def list_masters(
        self, *, active_only: bool = True, conn: aiosqlite.Connection | None = None
    ) -> list[Master]:
        sql = "SELECT * FROM masters" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY id"
        return [Master.from_row(r) for r in await self._db.fetch_all(sql, conn=conn)]

    async def get_master(self, master_id: int, *, conn: aiosqlite.Connection | None = None) -> Master | None:
        row = await self._db.fetch_one("SELECT * FROM masters WHERE id = ?", (master_id,), conn=conn)
        return Master.from_row(row) if row else None

    async def add_master(self, name: str, *, conn: aiosqlite.Connection | None = None) -> int:
        return await self._db.insert("INSERT INTO masters (name) VALUES (?)", (name,), conn=conn)

    async def update_master(
        self, master_id: int, *, name: str | None = None, is_active: bool | None = None
    ) -> None:
        await self._update(
            "masters", master_id, {"name": name, "is_active": None if is_active is None else int(is_active)}
        )

    # ---- links ----
    async def masters_for_service(
        self, service_id: int, *, conn: aiosqlite.Connection | None = None
    ) -> list[Master]:
        """Active masters that perform the service."""
        rows = await self._db.fetch_all(
            """
            SELECT m.* FROM masters m
            JOIN master_services ms ON ms.master_id = m.id
            WHERE ms.service_id = ? AND m.is_active = 1
            ORDER BY m.id
            """,
            (service_id,),
            conn=conn,
        )
        return [Master.from_row(r) for r in rows]

    async def master_service_ids(self, master_id: int) -> set[int]:
        rows = await self._db.fetch_all(
            "SELECT service_id FROM master_services WHERE master_id = ?", (master_id,)
        )
        return {row["service_id"] for row in rows}

    async def link_master_service(
        self, master_id: int, service_id: int, *, conn: aiosqlite.Connection | None = None
    ) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO master_services (master_id, service_id) VALUES (?, ?)",
            (master_id, service_id),
            conn=conn,
        )

    async def toggle_master_service(self, master_id: int, service_id: int) -> bool:
        """Flip the link. Returns True if the master now performs the service."""
        async with self._db.transaction() as conn:
            row = await self._db.fetch_one(
                "SELECT 1 FROM master_services WHERE master_id = ? AND service_id = ?",
                (master_id, service_id),
                conn=conn,
            )
            if row:
                await self._db.execute(
                    "DELETE FROM master_services WHERE master_id = ? AND service_id = ?",
                    (master_id, service_id),
                    conn=conn,
                )
                return False
            await self.link_master_service(master_id, service_id, conn=conn)
            return True

    # ---- helpers ----
    async def _update(self, table: str, row_id: int, fields: dict[str, object]) -> None:
        """UPDATE only the given non-None columns. Table and column names are code constants."""
        values = {key: value for key, value in fields.items() if value is not None}
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        await self._db.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?", (*values.values(), row_id)  # noqa: S608
        )
