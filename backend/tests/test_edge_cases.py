import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app import db as db_mod
from app.memory_redis import MemoryRedis
from app.services import snapshot_service
from app.services.market_cache import write_live_tick
from app.signal_engine import log_volume_zscore


USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def _tick(timestamp: datetime) -> dict[str, object]:
    return {
        "symbol": "INFY",
        "sector": "IT",
        "price": 100.0,
        "previous_price": 99.0,
        "volume": 1_000.0,
        "previous_volume": 1_000.0,
        "rsi": 50.0,
        "nifty_price": 100.0,
        "sector_price": 100.0,
        "previous_sector_price": 99.0,
        "ts": timestamp.isoformat(),
    }


def test_session_gap_calculation(monkeypatch):
    for hours_away in (1, 24):
        asyncio.run(_assert_session_gap(hours_away, monkeypatch))


async def _assert_session_gap(hours_away, monkeypatch):
    redis = MemoryRedis()
    await write_live_tick(redis, _tick(datetime.now(timezone.utc)))
    last_seen = datetime.now(timezone.utc) - timedelta(hours=hours_away)

    monkeypatch.setattr(snapshot_service, "get_redis", lambda: redis)
    async def load_user(_user_id):
        return {"last_seen_at": last_seen}

    async def load_watchlist(_user_id):
        return ["INFY"]

    async def load_snapshots(_user_id):
        return {}

    monkeypatch.setattr(snapshot_service, "_load_user", load_user)
    monkeypatch.setattr(snapshot_service, "_load_watchlist", load_watchlist)
    monkeypatch.setattr(snapshot_service, "_load_snapshots", load_snapshots)

    payload = await snapshot_service.get_session_delta(USER_ID)

    assert payload["time_away"] == f"{hours_away}h 0m"


@pytest.mark.parametrize("volume", [0.0, 1_000.0])
def test_zero_variance_volume_z_score_is_finite(volume):
    score = log_volume_zscore(volume, [1_000.0] * 30)

    assert score == 0.0 if volume == 1_000.0 else score < 0.0
    assert score == score


def test_stale_tick_is_marked_delayed(monkeypatch):
    asyncio.run(_assert_stale_tick(monkeypatch))


async def _assert_stale_tick(monkeypatch):
    redis = MemoryRedis()
    stale_timestamp = datetime.now(timezone.utc) - timedelta(seconds=61)
    await write_live_tick(redis, _tick(stale_timestamp))

    monkeypatch.setattr(snapshot_service, "get_redis", lambda: redis)
    async def load_user(_user_id):
        return {"last_seen_at": None}

    async def load_watchlist(_user_id):
        return ["INFY"]

    async def load_snapshots(_user_id):
        return {}

    monkeypatch.setattr(snapshot_service, "_load_user", load_user)
    monkeypatch.setattr(snapshot_service, "_load_watchlist", load_watchlist)
    monkeypatch.setattr(snapshot_service, "_load_snapshots", load_snapshots)
    monkeypatch.setattr(db_mod, "pool", None)

    payload = await snapshot_service.get_session_delta(USER_ID)
    stock = payload["watchlist"][0]

    assert stock["data_quality"]["is_stale"] is True
    assert stock["status"] == "DELAYED"
