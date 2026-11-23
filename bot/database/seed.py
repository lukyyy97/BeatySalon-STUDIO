"""Demo data inserted on the very first start so the bot can be tested immediately."""
import logging

from bot.database.db import Database

logger = logging.getLogger(__name__)

_SERVICES = [
    ("Фарбування волосся", 1800, 150),
    ("Стрижка", 600, 60),
    ("Манікюр", 500, 90),
]

# name -> (services, weekdays 0=Mon..6=Sun, start, end, break_start, break_end)
_MASTERS = [
    ("Олена Коваленко", ["Фарбування волосся", "Стрижка"], range(0, 5), "09:00", "18:00", "13:00", "14:00"),
    ("Ірина Шевчук", ["Стрижка", "Фарбування волосся"], range(1, 6), "10:00", "19:00", "14:00", "15:00"),
    ("Марія Бондаренко", ["Манікюр"], range(0, 5), "10:00", "19:00", "14:00", "15:00"),
    ("Анна Мельник", ["Манікюр"], range(2, 7), "09:00", "17:00", None, None),
]


async def seed_if_empty(db: Database) -> None:
    """Fill services, masters and schedules once (tracked in the `meta` table)."""
    async with db.transaction() as conn:
        if await db.fetch_one("SELECT 1 FROM meta WHERE key = 'seeded'", conn=conn):
            return

        service_ids: dict[str, int] = {}
        for name, price, duration in _SERVICES:
            service_ids[name] = await db.insert(
                "INSERT INTO services (name, price, duration_min) VALUES (?, ?, ?)",
                (name, price, duration),
                conn=conn,
            )

        for name, services, weekdays, start, end, break_start, break_end in _MASTERS:
            master_id = await db.insert("INSERT INTO masters (name) VALUES (?)", (name,), conn=conn)
            for service_name in services:
                await db.execute(
                    "INSERT INTO master_services (master_id, service_id) VALUES (?, ?)",
                    (master_id, service_ids[service_name]),
                    conn=conn,
                )
            for weekday in weekdays:
                await db.execute(
                    """
                    INSERT INTO work_schedule (master_id, weekday, start_time, end_time, break_start, break_end)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (master_id, weekday, start, end, break_start, break_end),
                    conn=conn,
                )

        await db.execute("INSERT INTO meta (key, value) VALUES ('seeded', '1')", conn=conn)
    logger.info("Demo data inserted (services, masters, schedules)")
