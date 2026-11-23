"""Thin async SQLite wrapper.

Every operation uses its own short-lived connection (autocommit mode). Multi-statement
atomic work goes through `transaction()` which takes SQLite's write lock up front
(`BEGIN IMMEDIATE`), so concurrent writers are serialised by the database itself.
"""
import contextlib
import logging
import sqlite3
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from bot.database.schema import SCHEMA

logger = logging.getLogger(__name__)

Params = Sequence[Any]

# How long a writer waits for SQLite's write lock before giving up (seconds).
_BUSY_TIMEOUT_SECONDS = 15


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path

    async def init(self) -> None:
        """Create the data directory and all tables (idempotent)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connection() as conn:
            async with conn.execute("PRAGMA journal_mode = WAL") as cursor:
                await cursor.fetchone()
            await conn.executescript(SCHEMA)
        logger.info("Database ready: %s", self._path)

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        # The busy timeout is set through `timeout=` (installed before any statement runs).
        # Do NOT leave PRAGMA cursors unread: an unfinished statement made `BEGIN IMMEDIATE`
        # fail instantly with "database is locked" instead of waiting for the lock.
        conn = await aiosqlite.connect(
            str(self._path), timeout=_BUSY_TIMEOUT_SECONDS, isolation_level=None
        )
        try:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("PRAGMA foreign_keys = ON") as cursor:
                await cursor.fetchall()
            yield conn
        finally:
            await conn.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Atomic block holding the write lock. Rolls back on any exception."""
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                # SQLite may already have rolled back after a hard error: never mask the original one.
                with contextlib.suppress(sqlite3.Error):
                    await conn.execute("ROLLBACK")
                raise
            else:
                await conn.execute("COMMIT")

    @asynccontextmanager
    async def _use(self, conn: aiosqlite.Connection | None) -> AsyncIterator[aiosqlite.Connection]:
        if conn is not None:
            yield conn
        else:
            async with self.connection() as new_conn:
                yield new_conn

    async def fetch_one(
        self, sql: str, params: Params = (), *, conn: aiosqlite.Connection | None = None
    ) -> aiosqlite.Row | None:
        async with self._use(conn) as active, active.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetch_all(
        self, sql: str, params: Params = (), *, conn: aiosqlite.Connection | None = None
    ) -> list[aiosqlite.Row]:
        async with self._use(conn) as active, active.execute(sql, params) as cursor:
            return list(await cursor.fetchall())

    async def execute(
        self, sql: str, params: Params = (), *, conn: aiosqlite.Connection | None = None
    ) -> int:
        """Run a statement, return the number of affected rows."""
        async with self._use(conn) as active, active.execute(sql, params) as cursor:
            return cursor.rowcount

    async def insert(
        self, sql: str, params: Params = (), *, conn: aiosqlite.Connection | None = None
    ) -> int:
        """Run an INSERT, return the new row id."""
        async with self._use(conn) as active, active.execute(sql, params) as cursor:
            if cursor.lastrowid is None:  # pragma: no cover - defensive
                raise RuntimeError("INSERT did not produce a row id")
            return int(cursor.lastrowid)
