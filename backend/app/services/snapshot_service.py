from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import numpy as np

from app import db as db_mod
from app.db import get_memory_db, get_pool, get_redis
from app.mock_market_feed import SECTOR_INDEX_LEVELS, UNIVERSE
from app.services.market_cache import read_history, read_live_tick, write_live_tick
from app.services.notification_service import send_high_attention_alert
from app.signal_engine import compute_mci_score


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _pct(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return _round(100.0 * (new - old) / old)


def _format_time_away(last_seen: datetime | None) -> str:
    if last_seen is None:
        return "Just now"
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    elapsed = max(datetime.now(timezone.utc) - last_seen, timedelta(0))
    total_minutes = int(elapsed.total_seconds() // 60)
    return f"{total_minutes // 60}h {total_minutes % 60}m"


def _data_quality(live: dict[str, Any]) -> dict[str, Any]:
    timestamp = live.get("ts")
    if not timestamp:
        return {"is_stale": True, "age_seconds": None}
    try:
        tick_time = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if tick_time.tzinfo is None:
            tick_time = tick_time.replace(tzinfo=timezone.utc)
        age_seconds = max((datetime.now(timezone.utc) - tick_time).total_seconds(), 0.0)
    except ValueError:
        return {"is_stale": True, "age_seconds": None}
    return {
        "is_stale": age_seconds > 60,
        "age_seconds": _round(age_seconds, 2),
    }


async def _dispatch_high_attention_alerts(payloads: list[dict[str, Any]]) -> None:
    alerts = [
        asyncio.to_thread(
            send_high_attention_alert,
            payload["symbol"],
            payload["mci"],
            (
                f"{payload['symbol']} is showing a meaningful change: "
                f"MCI {payload['mci']:.0f}/100 with {payload['price_delta_pct']:.2f}% price movement."
            ),
        )
        for payload in payloads
        if payload["mci"] >= 80 and not payload["data_quality"]["is_stale"]
    ]
    if alerts:
        await asyncio.gather(*alerts, return_exceptions=True)


async def _load_user(user_id: UUID) -> dict[str, Any] | None:
    if db_mod.pool is not None:
        row = await get_pool().fetchrow(
            "SELECT id, name, email, last_seen_at FROM users WHERE id = $1",
            user_id,
        )
        return dict(row) if row else None
    return get_memory_db().get_user(user_id)


async def _load_watchlist(user_id: UUID) -> list[str]:
    if db_mod.pool is not None:
        rows = await get_pool().fetch(
            "SELECT symbol FROM watchlists WHERE user_id = $1 ORDER BY added_at",
            user_id,
        )
        return [row["symbol"] for row in rows]
    return get_memory_db().watchlist_symbols(user_id)


async def _load_snapshots(user_id: UUID) -> dict[str, dict[str, Any]]:
    if db_mod.pool is not None:
        rows = await get_pool().fetch(
            """
            SELECT DISTINCT ON (symbol)
                symbol, price, volume, rsi, nifty_price, sector_price, created_at
            FROM user_session_snapshots
            WHERE user_id = $1
            ORDER BY symbol, created_at DESC
            """,
            user_id,
        )
        return {row["symbol"]: dict(row) for row in rows}
    return get_memory_db().latest_snapshots(user_id)


def _engine_payload(
    symbol: str,
    live: dict[str, Any],
    snap: dict[str, Any] | None,
    prices: list[float],
    volumes: list[float],
) -> dict[str, Any]:
    baseline_price = float(snap["price"]) if snap and snap.get("price") is not None else live["previous_price"]
    baseline_volume = float(snap["volume"]) if snap and snap.get("volume") is not None else live["previous_volume"]
    baseline_sector = (
        float(snap["sector_price"])
        if snap and snap.get("sector_price") is not None
        else live["previous_sector_price"]
    )
    hist_prices = prices[:-1] if len(prices) > 2 else prices
    hist_volumes = volumes[:-1] if len(volumes) > 2 else volumes
    if not hist_prices:
        hist_prices = [baseline_price] * 24
    if not hist_volumes:
        hist_volumes = [baseline_volume] * 24

    mci = compute_mci_score(
        volume=live["volume"],
        historical_volumes=hist_volumes,
        price=live["price"],
        previous_price=baseline_price,
        historical_prices=hist_prices,
        sector_price=live["sector_price"],
        previous_sector_price=baseline_sector,
    )
    payload = {
        "symbol": symbol,
        "price": _round(live["price"], 2),
        "previous_price": _round(baseline_price, 2),
        "price_delta": _round(live["price"] - baseline_price, 2),
        "price_delta_pct": _pct(live["price"], baseline_price),
        "volume": int(live["volume"]),
        "previous_volume": int(baseline_volume),
        "volume_delta": int(live["volume"] - baseline_volume),
        "volume_delta_pct": _pct(live["volume"], baseline_volume),
        "rsi": _round(live["rsi"], 2),
        "nifty_price": _round(live["nifty_price"], 2),
        "sector_price": _round(live["sector_price"], 2),
        "previous_sector_price": _round(baseline_sector, 2),
        "z_volume": _round(mci.z_volume),
        "z_price": _round(mci.z_price),
        "sector_relative_delta": _round(mci.sector_relative_delta),
        "mci": _round(mci.mci, 2),
        "priority": str(mci.priority),
        "has_prior_snapshot": snap is not None,
    }
    payload["data_quality"] = _data_quality(live)
    payload["status"] = "DELAYED" if payload["data_quality"]["is_stale"] else "LIVE"
    return payload


async def get_session_delta(user_id: UUID) -> dict[str, Any]:
    user = await _load_user(user_id)
    if user is None:
        raise KeyError(f"user {user_id} not found")

    symbols = await _load_watchlist(user_id)
    snapshots = await _load_snapshots(user_id)
    redis = get_redis()
    ranked: list[dict[str, Any]] = []

    for symbol in symbols:
        live = await read_live_tick(redis, symbol)
        if live is None:
            continue
        prices, volumes = await read_history(redis, symbol)
        snap = snapshots.get(symbol)
        payload = _engine_payload(symbol, live, snap, prices, volumes)
        ranked.append(payload)

    ranked.sort(key=lambda row: row["mci"], reverse=True)
    await _dispatch_high_attention_alerts(ranked)
    last_seen = user.get("last_seen_at")
    return {
        "user_id": str(user_id),
        "last_seen_at": last_seen.isoformat() if last_seen else None,
        "time_away": _format_time_away(last_seen),
        "store": "memory" if db_mod.pool is None else "postgres",
        "count": len(ranked),
        "watchlist": ranked,
    }


async def checkout_session(user_id: UUID) -> dict[str, Any]:
    if db_mod.pool is None:
        get_memory_db().ensure_user(user_id)
    else:
        user = await _load_user(user_id)
        if user is None:
            raise KeyError(f"user {user_id} not found")

    symbols = await _load_watchlist(user_id)
    redis = get_redis()
    seen_at = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    for symbol in symbols:
        live = await read_live_tick(redis, symbol)
        if live is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "price": live["price"],
                "volume": int(live["volume"]),
                "rsi": live["rsi"],
                "nifty_price": live["nifty_price"],
                "sector_price": live["sector_price"],
                "created_at": seen_at,
            }
        )

    if db_mod.pool is not None:
        db = get_pool()
        async with db.acquire() as conn:
            async with conn.transaction():
                for row in rows:
                    await conn.execute(
                        """
                        INSERT INTO user_session_snapshots
                            (user_id, symbol, price, volume, rsi, nifty_price, sector_price, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        user_id,
                        row["symbol"],
                        row["price"],
                        row["volume"],
                        row["rsi"],
                        row["nifty_price"],
                        row["sector_price"],
                        seen_at,
                    )
                await conn.execute(
                    "UPDATE users SET last_seen_at = $2 WHERE id = $1",
                    user_id,
                    seen_at,
                )
    else:
        get_memory_db().replace_snapshots(user_id, rows, seen_at)

    return {
        "user_id": str(user_id),
        "checked_out_at": seen_at.isoformat(),
        "symbols": [row["symbol"] for row in rows],
        "count": len(rows),
    }


async def engine_breakdown_for_symbol(symbol: str, user_id: UUID | None = None) -> dict[str, Any]:
    live = await read_live_tick(get_redis(), symbol.upper())
    if live is None:
        raise KeyError(f"no live market state for {symbol}")
    prices, volumes = await read_history(get_redis(), symbol.upper())
    snap = None
    if user_id is not None:
        snap = (await _load_snapshots(user_id)).get(symbol.upper())
    payload = _engine_payload(symbol.upper(), live, snap, prices, volumes)
    await _dispatch_high_attention_alerts([payload])
    return payload


async def seed_demo_state() -> None:
    """Baseline last-visit snapshots plus a noisier live tape in Redis."""
    redis = get_redis()
    rng = np.random.default_rng(11)
    nifty = 24850.0
    now = datetime.now(timezone.utc)
    last_seen = now - timedelta(hours=6)

    snapshot_rows: list[dict[str, Any]] = []
    for row in UNIVERSE:
        symbol = str(row["symbol"])
        base_price = float(row["price"])
        base_vol = float(row["adv"]) / 23400.0
        sector_px = float(live_sector_price(row["sector"]))
        hist_px = [max(0.01, base_price * (1 + float(rng.normal(0, 0.004)))) for _ in range(40)]
        hist_vol = [max(1.0, base_vol * float(rng.lognormal(0, 0.08))) for _ in range(40)]

        live_price = hist_px[-1]
        live_vol = hist_vol[-1]
        if symbol == "RELIANCE":
            live_price = base_price * 0.94
            live_vol = base_vol * 2.8
        elif symbol == "TATAMOTORS":
            live_price = base_price * 1.012
            live_vol = base_vol * 1.6

        tick = {
            "symbol": symbol,
            "sector": row["sector"],
            "price": round(live_price, 2),
            "previous_price": round(base_price, 2),
            "volume": int(live_vol),
            "previous_volume": int(base_vol),
            "rsi": 42.5 if symbol == "RELIANCE" else 54.0,
            "nifty_price": nifty,
            "sector_price": round(sector_px * (0.995 if symbol == "RELIANCE" else 1.001), 2),
            "previous_sector_price": round(sector_px, 2),
            "ts": now.isoformat(),
        }

        for px, vol in zip(hist_px, hist_vol, strict=False):
            await redis.rpush(f"market:hist:{symbol}:prices", round(px, 2))
            await redis.rpush(f"market:hist:{symbol}:volumes", int(vol))
        await write_live_tick(redis, tick)

        snapshot_rows.append(
            {
                "symbol": symbol,
                "price": base_price,
                "volume": int(base_vol),
                "rsi": 51.0,
                "nifty_price": nifty,
                "sector_price": sector_px,
                "created_at": last_seen,
            }
        )

    demo_id = UUID("00000000-0000-4000-8000-000000000001")
    watch = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "TATAMOTORS"]
    if db_mod.pool is not None:
        db = get_pool()
        await db.execute(
            """
            INSERT INTO users (id, name, email, last_seen_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at
            """,
            demo_id,
            "Demo Trader",
            "demo@groww.signal",
            last_seen,
        )
        for symbol in watch:
            await db.execute(
                """
                INSERT INTO watchlists (user_id, symbol)
                VALUES ($1, $2)
                ON CONFLICT (user_id, symbol) DO NOTHING
                """,
                demo_id,
                symbol,
            )
        await db.execute("DELETE FROM user_session_snapshots WHERE user_id = $1", demo_id)
        for row in snapshot_rows:
            if row["symbol"] not in watch:
                continue
            await db.execute(
                """
                INSERT INTO user_session_snapshots
                    (user_id, symbol, price, volume, rsi, nifty_price, sector_price, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                demo_id,
                row["symbol"],
                row["price"],
                row["volume"],
                row["rsi"],
                row["nifty_price"],
                row["sector_price"],
                last_seen,
            )
    elif db_mod.memory_db is not None:
        db_mod.memory_db.users[demo_id]["last_seen_at"] = last_seen
        db_mod.memory_db.watchlists[demo_id] = watch
        db_mod.memory_db.snapshots[demo_id] = [
            row for row in snapshot_rows if row["symbol"] in watch
        ]


def live_sector_price(sector: str) -> float:
    return float(SECTOR_INDEX_LEVELS.get(sector, 10000.0))
