"""Mock NSE tick stream with controllable volume spikes and earnings gaps.

Publishes JSON ticks to Redis Pub/Sub channel `market:ticks`.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import numpy as np

MARKET_TICKS_CHANNEL = "market:ticks"
VOLUME_SPIKE_MULTIPLIER = 2.8

# Approximate cash-market levels so GBM paths look like India names, not toys.
UNIVERSE: tuple[dict[str, Any], ...] = (
    {"symbol": "INFY", "sector": "IT", "price": 1875.0, "adv": 4_800_000},
    {"symbol": "TATAMOTORS", "sector": "AUTO", "price": 980.0, "adv": 9_200_000},
    {"symbol": "HDFCBANK", "sector": "BANK", "price": 1670.0, "adv": 12_500_000},
    {"symbol": "RELIANCE", "sector": "ENERGY", "price": 2920.0, "adv": 6_100_000},
    {"symbol": "TCS", "sector": "IT", "price": 4125.0, "adv": 2_400_000},
    {"symbol": "ICICIBANK", "sector": "BANK", "price": 1240.0, "adv": 11_000_000},
    {"symbol": "SBIN", "sector": "BANK", "price": 820.0, "adv": 14_800_000},
    {"symbol": "BHARTIARTL", "sector": "TELECOM", "price": 1760.0, "adv": 5_500_000},
    {"symbol": "ITC", "sector": "FMCG", "price": 475.0, "adv": 10_200_000},
    {"symbol": "LT", "sector": "CAPITAL_GOODS", "price": 3550.0, "adv": 1_900_000},
    {"symbol": "AXISBANK", "sector": "BANK", "price": 1185.0, "adv": 7_400_000},
    {"symbol": "HINDUNILVR", "sector": "FMCG", "price": 2480.0, "adv": 1_300_000},
    {"symbol": "KOTAKBANK", "sector": "BANK", "price": 1795.0, "adv": 3_600_000},
    {"symbol": "BAJFINANCE", "sector": "NBFC", "price": 7200.0, "adv": 1_100_000},
    {"symbol": "MARUTI", "sector": "AUTO", "price": 12850.0, "adv": 480_000},
)

SECTOR_INDEX_LEVELS: dict[str, float] = {
    "IT": 42_500.0,
    "AUTO": 24_800.0,
    "BANK": 51_200.0,
    "ENERGY": 38_400.0,
    "TELECOM": 3_150.0,
    "FMCG": 57_900.0,
    "CAPITAL_GOODS": 66_200.0,
    "NBFC": 23_100.0,
}


class TickPublisher(Protocol):
    async def publish(self, channel: str, message: str) -> int: ...


@dataclass
class AnomalyTriggers:
    """One-shot (or N-tick) shocks applied on the next generated ticks."""

    volume_spike: dict[str, int] = field(default_factory=dict)
    earnings_gap_down: dict[str, float] = field(default_factory=dict)

    def arm_volume_spike(self, symbol: str, ticks: int = 1) -> None:
        self.volume_spike[symbol] = max(1, ticks)

    def arm_earnings_gap_down(self, symbol: str, gap: float = -0.06) -> None:
        if gap >= 0:
            raise ValueError("earnings gap-down must be a negative return")
        self.earnings_gap_down[symbol] = gap


@dataclass
class _NameState:
    symbol: str
    sector: str
    price: float
    adv: float
    prev_price: float
    sector_price: float
    prev_sector_price: float


class MockMarketFeed:
    def __init__(
        self,
        publisher: TickPublisher | None = None,
        *,
        channel: str = MARKET_TICKS_CHANNEL,
        seed: int = 42,
        dt: float = 1.0 / (6.5 * 60 * 60),
        annual_vol: float = 0.22,
        anomalies: AnomalyTriggers | None = None,
    ) -> None:
        self._publisher = publisher
        self.channel = channel
        self.rng = np.random.default_rng(seed)
        self.dt = dt
        self.annual_vol = annual_vol
        self.anomalies = anomalies or AnomalyTriggers()
        self._names = [
            _NameState(
                symbol=row["symbol"],
                sector=row["sector"],
                price=float(row["price"]),
                adv=float(row["adv"]),
                prev_price=float(row["price"]),
                sector_price=SECTOR_INDEX_LEVELS[row["sector"]],
                prev_sector_price=SECTOR_INDEX_LEVELS[row["sector"]],
            )
            for row in UNIVERSE
        ]

    @property
    def symbols(self) -> list[str]:
        return [name.symbol for name in self._names]

    def trigger_volume_spike(self, symbol: str, ticks: int = 1) -> None:
        self.anomalies.arm_volume_spike(symbol, ticks)

    def trigger_earnings_gap_down(self, symbol: str, gap: float = -0.06) -> None:
        self.anomalies.arm_earnings_gap_down(symbol, gap)

    def next_ticks(self) -> list[dict[str, Any]]:
        return [self._step(name) for name in self._names]

    async def publish_ticks(self, ticks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        batch = ticks if ticks is not None else self.next_ticks()
        if self._publisher is None:
            raise RuntimeError("no Redis publisher configured")
        payload = json.dumps(batch)
        await self._publisher.publish(self.channel, payload)
        return batch

    async def run(self, interval_seconds: float = 0.25, loops: int | None = None) -> None:
        remaining = loops
        while remaining is None or remaining > 0:
            await self.publish_ticks()
            if remaining is not None:
                remaining -= 1
            await asyncio.sleep(interval_seconds)

    def _step(self, name: _NameState) -> dict[str, Any]:
        name.prev_price = name.price
        name.prev_sector_price = name.sector_price

        sigma = self.annual_vol * np.sqrt(self.dt)
        shock = float(self.rng.normal(0.0, sigma))
        sector_shock = float(self.rng.normal(0.0, sigma * 0.7))

        remaining = self.anomalies.volume_spike.get(name.symbol, 0)
        spike = remaining > 0
        if spike:
            remaining -= 1
            if remaining:
                self.anomalies.volume_spike[name.symbol] = remaining
            else:
                self.anomalies.volume_spike.pop(name.symbol, None)

        gap = self.anomalies.earnings_gap_down.pop(name.symbol, None)
        if gap is not None:
            shock = float(gap)

        name.price = max(0.01, name.price * float(np.exp(shock)))
        name.sector_price = max(0.01, name.sector_price * float(np.exp(sector_shock)))

        base_volume = max(1, int(round(float(self.rng.lognormal(np.log(name.adv / 23400.0), 0.25)))))
        volume = (
            int(round(base_volume * VOLUME_SPIKE_MULTIPLIER)) if spike else base_volume
        )

        return {
            "symbol": name.symbol,
            "sector": name.sector,
            "price": round(name.price, 2),
            "previous_price": round(name.prev_price, 2),
            "volume": int(volume),
            "sector_price": round(name.sector_price, 2),
            "previous_sector_price": round(name.prev_sector_price, 2),
            "anomaly": "volume_spike" if spike else ("earnings_gap_down" if gap is not None else None),
            "ts": datetime.now(timezone.utc).isoformat(),
            "seq": time.time_ns(),
        }


async def connect_publisher(redis_url: str) -> Any:
    from redis.asyncio import Redis

    return Redis.from_url(redis_url, decode_responses=True)


async def main() -> None:
    from app.config import settings

    redis = await connect_publisher(settings.redis_url)
    feed = MockMarketFeed(publisher=redis)
    try:
        await feed.run()
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
