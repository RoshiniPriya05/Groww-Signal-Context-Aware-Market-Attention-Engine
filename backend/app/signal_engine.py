"""Attention scores from volume, price, and sector-relative moves.

Welford updates are O(1). RollingWelford is O(1) per tick for a fixed window
(add newest, remove oldest) without rescanning history.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

import numpy as np

MAX_Z = 8.0
STD_EPS = 1e-12
VOLUME_WEIGHT = 0.45
PRICE_WEIGHT = 0.35
SECTOR_WEIGHT = 0.20
# |Z|~3 and ~2% sector-relative move sit near the high end of the raw scale.
MCI_SCALE = 2.4
SECTOR_RETURN_SCALE = 0.02


class Priority(StrEnum):
    CRITICAL = "CRITICAL"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class MCIResult:
    z_volume: float
    z_price: float
    sector_relative_delta: float
    mci: float
    priority: Priority


class WelfordAccumulator:
    """Numerically stable online mean / variance (Knuth / Welford)."""

    __slots__ = ("_n", "_mean", "_m2")

    def __init__(self) -> None:
        self._n = 0
        self._mean = 0.0
        self._m2 = 0.0

    def reset(self) -> None:
        self._n = 0
        self._mean = 0.0
        self._m2 = 0.0

    def update(self, x: float) -> None:
        value = float(x)
        self._n += 1
        delta = value - self._mean
        self._mean += delta / self._n
        delta2 = value - self._mean
        self._m2 += delta * delta2

    def remove(self, x: float) -> None:
        """Drop one observation (needed for an O(1) sliding window)."""
        if self._n <= 0:
            raise ValueError("cannot remove from an empty accumulator")
        if self._n == 1:
            self.reset()
            return
        value = float(x)
        n_old = self._n
        self._n -= 1
        delta = value - self._mean
        self._mean = (n_old * self._mean - value) / self._n
        delta2 = value - self._mean
        self._m2 = max(0.0, self._m2 - delta * delta2)

    @property
    def n(self) -> int:
        return self._n

    @property
    def mean(self) -> float:
        return self._mean if self._n else 0.0

    @property
    def sample_variance(self) -> float:
        if self._n < 2:
            return 0.0
        return self._m2 / (self._n - 1)

    @property
    def sample_std(self) -> float:
        return float(np.sqrt(self.sample_variance))


class RollingWelford:
    """Fixed-window mean and sample std with O(1) updates."""

    __slots__ = ("_window", "_values", "_idx", "_filled", "_stats")

    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("window must be at least 2")
        self._window = window
        self._values = np.zeros(window, dtype=np.float64)
        self._idx = 0
        self._filled = 0
        self._stats = WelfordAccumulator()

    def update(self, x: float) -> WelfordAccumulator:
        value = float(x)
        if self._filled == self._window:
            self._stats.remove(float(self._values[self._idx]))
        else:
            self._filled += 1
        self._values[self._idx] = value
        self._stats.update(value)
        self._idx = (self._idx + 1) % self._window
        return self._stats

    @property
    def stats(self) -> WelfordAccumulator:
        return self._stats


def _safe_z(value: float, mean: float, std: float) -> float:
    """Z-score that never divides by zero; constant series that then jumps saturates."""
    if std < STD_EPS:
        if abs(value - mean) < STD_EPS:
            return 0.0
        return float(np.copysign(MAX_Z, value - mean))
    return float(np.clip((value - mean) / std, -MAX_Z, MAX_Z))


def _welford_of(values: Sequence[float]) -> WelfordAccumulator:
    acc = WelfordAccumulator()
    for item in values:
        acc.update(float(item))
    return acc


def log_volume_zscore(volume: float, historical_volumes: Sequence[float]) -> float:
    """Z_V of log1p(volume) versus Welford stats of historical log volumes."""
    hist = _welford_of(np.log1p(np.asarray(historical_volumes, dtype=np.float64)))
    return _safe_z(float(np.log1p(max(volume, 0.0))), hist.mean, hist.sample_std)


def volatility_adjusted_price_zscore(
    price: float,
    previous_price: float,
    historical_prices: Sequence[float],
) -> float:
    """Z_P = current log-return / sample std of historical log-returns."""
    prices = np.asarray(historical_prices, dtype=np.float64)
    if previous_price <= 0 or price <= 0:
        return 0.0
    current_return = float(np.log(price / previous_price))
    if prices.size < 2:
        return _safe_z(current_return, 0.0, 0.0)

    positive = prices[prices > 0]
    if positive.size < 2:
        return _safe_z(current_return, 0.0, 0.0)
    log_returns = np.diff(np.log(positive))
    stats = _welford_of(log_returns)
    return _safe_z(current_return, stats.mean, stats.sample_std)


def sector_relative_delta(
    price: float,
    previous_price: float,
    sector_price: float,
    previous_sector_price: float,
) -> float:
    """Δ_stock − Δ_sector using simple returns."""
    if previous_price <= 0 or previous_sector_price <= 0:
        return 0.0
    stock_delta = (price - previous_price) / previous_price
    sector_delta = (sector_price - previous_sector_price) / previous_sector_price
    return float(stock_delta - sector_delta)


def _priority_for(mci: float) -> Priority:
    if mci >= 75:
        return Priority.CRITICAL
    if mci >= 50:
        return Priority.MEDIUM
    return Priority.LOW


def _normalize_mci(z_volume: float, z_price: float, relative: float) -> float:
    raw = (
        VOLUME_WEIGHT * abs(z_volume)
        + PRICE_WEIGHT * abs(z_price)
        + SECTOR_WEIGHT * (abs(relative) / SECTOR_RETURN_SCALE)
    )
    score = 100.0 * float(np.tanh(raw / MCI_SCALE))
    return float(np.clip(score, 0.0, 100.0))


def compute_mci_score(
    volume: float,
    historical_volumes: Sequence[float],
    price: float,
    previous_price: float,
    historical_prices: Sequence[float],
    sector_price: float,
    previous_sector_price: float,
) -> MCIResult:
    z_v = log_volume_zscore(volume, historical_volumes)
    z_p = volatility_adjusted_price_zscore(price, previous_price, historical_prices)
    relative = sector_relative_delta(
        price, previous_price, sector_price, previous_sector_price
    )
    mci = _normalize_mci(z_v, z_p, relative)
    return MCIResult(
        z_volume=z_v,
        z_price=z_p,
        sector_relative_delta=relative,
        mci=mci,
        priority=_priority_for(mci),
    )
