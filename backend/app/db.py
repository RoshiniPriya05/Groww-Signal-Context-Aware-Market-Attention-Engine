import asyncio

import asyncpg
from redis.asyncio import Redis

from app.config import settings
from app.memory_db import MemoryDatabase
from app.memory_redis import MemoryRedis

pool: asyncpg.Pool | None = None
redis: Redis | MemoryRedis | None = None
memory_db: MemoryDatabase | None = None
using_memory_store = False


async def connect() -> None:
    global pool, redis, memory_db, using_memory_store
    using_memory_store = False
    memory_db = None

    try:
        pool = await asyncio.wait_for(
            asyncpg.create_pool(
                settings.database_url,
                min_size=1,
                max_size=10,
                timeout=3,
                command_timeout=5,
            ),
            timeout=4,
        )
        assert pool is not None
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        if pool is not None:
            await pool.close()
        pool = None
        using_memory_store = True
        memory_db = MemoryDatabase()

    client = None
    try:
        client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await asyncio.wait_for(client.ping(), timeout=3)
        redis = client
    except Exception:
        try:
            if client is not None:
                await client.aclose()
        except Exception:
            pass
        redis = MemoryRedis()
        using_memory_store = True
        if memory_db is None:
            memory_db = MemoryDatabase()


async def disconnect() -> None:
    global pool, redis, memory_db, using_memory_store
    if pool is not None:
        await pool.close()
        pool = None
    if redis is not None:
        await redis.aclose()
        redis = None
    memory_db = None
    using_memory_store = False


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    return pool


def get_redis() -> Redis | MemoryRedis:
    if redis is None:
        raise RuntimeError("Redis client is not initialized")
    return redis


def get_memory_db() -> MemoryDatabase:
    if memory_db is None:
        raise RuntimeError("Memory database is not initialized")
    return memory_db
