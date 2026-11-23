"""Per-key asyncio locks (used to serialise actions of a single user)."""
import asyncio


class KeyedLocks:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    def get(self, key: int) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())
