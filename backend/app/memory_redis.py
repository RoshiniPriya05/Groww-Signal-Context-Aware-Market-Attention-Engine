"""In-memory Redis stand-in used when a real broker is unavailable."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class MemoryRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._hash: dict[str, dict[str, str]] = defaultdict(dict)
        self._list: dict[str, list[str]] = defaultdict(list)

    async def ping(self) -> bool:
        return True

    async def hset(self, name: str, mapping: dict[str, Any] | None = None, **kwargs: Any) -> int:
        payload = {**(mapping or {}), **kwargs}
        store = self._hash[name]
        for key, value in payload.items():
            store[str(key)] = str(value)
        return len(payload)

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._hash.get(name, {}))

    async def rpush(self, name: str, *values: Any) -> int:
        self._list[name].extend(str(v) for v in values)
        return len(self._list[name])

    async def lrange(self, name: str, start: int, end: int) -> list[str]:
        data = self._list.get(name, [])
        if end == -1:
            return data[start:]
        return data[start : end + 1]

    async def ltrim(self, name: str, start: int, end: int) -> bool:
        data = self._list.get(name, [])
        if end == -1:
            self._list[name] = data[start:]
        else:
            self._list[name] = data[start : end + 1]
        return True

    async def publish(self, channel: str, message: str) -> int:
        return 0

    async def aclose(self) -> None:
        return None
