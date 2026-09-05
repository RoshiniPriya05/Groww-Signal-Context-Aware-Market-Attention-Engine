"""One-shot connectivity check for local Postgres and Redis."""

import asyncio
import os
import sys

import asyncpg
from redis.asyncio import Redis

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://groww:groww@localhost:5432/groww_signal"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def main() -> int:
    errors: list[str] = []

    try:
        conn = await asyncpg.connect(DATABASE_URL, timeout=5)
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        names = [row["table_name"] for row in tables]
        print(f"postgres: ok  tables={names}")
        await conn.close()
    except Exception as exc:
        errors.append(f"postgres: {exc}")
        print(f"postgres: failed  {exc}")

    try:
        client = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
        pong = await client.ping()
        print(f"redis: ok  ping={pong}")
        await client.aclose()
    except Exception as exc:
        errors.append(f"redis: {exc}")
        print(f"redis: failed  {exc}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
