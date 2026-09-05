from __future__ import annotations

from typing import Any

from app.mock_market_feed import UNIVERSE

LIVE_KEY = "market:live:{symbol}"
HIST_PRICES_KEY = "market:hist:{symbol}:prices"
HIST_VOLUMES_KEY = "market:hist:{symbol}:volumes"
HIST_KEEP = 120


def live_key(symbol: str) -> str:
    return LIVE_KEY.format(symbol=symbol.upper())


def hist_prices_key(symbol: str) -> str:
    return HIST_PRICES_KEY.format(symbol=symbol.upper())


def hist_volumes_key(symbol: str) -> str:
    return HIST_VOLUMES_KEY.format(symbol=symbol.upper())


async def write_live_tick(redis: Any, tick: dict[str, Any]) -> None:
    symbol = str(tick["symbol"]).upper()
    mapping = {
        "symbol": symbol,
        "sector": tick.get("sector", ""),
        "price": tick["price"],
        "previous_price": tick.get("previous_price", tick["price"]),
        "volume": tick["volume"],
        "previous_volume": tick.get("previous_volume", tick["volume"]),
        "rsi": tick.get("rsi", 50),
        "nifty_price": tick.get("nifty_price", 0),
        "sector_price": tick.get("sector_price", 0),
        "previous_sector_price": tick.get("previous_sector_price", tick.get("sector_price", 0)),
        "ts": tick.get("ts", ""),
    }
    await redis.hset(live_key(symbol), mapping=mapping)
    await redis.rpush(hist_prices_key(symbol), mapping["price"])
    await redis.rpush(hist_volumes_key(symbol), mapping["volume"])
    await redis.ltrim(hist_prices_key(symbol), -HIST_KEEP, -1)
    await redis.ltrim(hist_volumes_key(symbol), -HIST_KEEP, -1)


async def read_live_tick(redis: Any, symbol: str) -> dict[str, Any] | None:
    raw = await redis.hgetall(live_key(symbol))
    if not raw:
        return None
    return {
        "symbol": raw.get("symbol", symbol.upper()),
        "sector": raw.get("sector", ""),
        "price": float(raw["price"]),
        "previous_price": float(raw.get("previous_price", raw["price"])),
        "volume": float(raw["volume"]),
        "previous_volume": float(raw.get("previous_volume", raw["volume"])),
        "rsi": float(raw.get("rsi", 50)),
        "nifty_price": float(raw.get("nifty_price", 0)),
        "sector_price": float(raw.get("sector_price", 0)),
        "previous_sector_price": float(raw.get("previous_sector_price", raw.get("sector_price", 0))),
        "ts": raw.get("ts", ""),
    }


async def read_history(redis: Any, symbol: str) -> tuple[list[float], list[float]]:
    prices = [float(x) for x in await redis.lrange(hist_prices_key(symbol), 0, -1)]
    volumes = [float(x) for x in await redis.lrange(hist_volumes_key(symbol), 0, -1)]
    return prices, volumes


def universe_symbols() -> list[str]:
    return [str(row["symbol"]) for row in UNIVERSE]
