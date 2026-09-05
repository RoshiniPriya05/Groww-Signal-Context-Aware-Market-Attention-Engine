from __future__ import annotations

import math

import numpy as np

from app.mock_market_feed import VOLUME_SPIKE_MULTIPLIER, MockMarketFeed, UNIVERSE
from app.signal_engine import (
    MAX_Z,
    Priority,
    RollingWelford,
    WelfordAccumulator,
    _normalize_mci,
    _priority_for,
    compute_mci_score,
    log_volume_zscore,
    sector_relative_delta,
    volatility_adjusted_price_zscore,
)


def test_welford_matches_numpy_sample_moments() -> None:
    rng = np.random.default_rng(7)
    xs = rng.normal(100.0, 8.0, size=250)
    acc = WelfordAccumulator()
    for x in xs:
        acc.update(float(x))
    assert acc.n == 250
    np.testing.assert_allclose(acc.mean, xs.mean(), rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(acc.sample_std, xs.std(ddof=1), rtol=1e-12, atol=1e-12)


def test_welford_single_observation_has_zero_std() -> None:
    acc = WelfordAccumulator()
    acc.update(42.0)
    assert acc.mean == 42.0
    assert acc.sample_variance == 0.0
    assert acc.sample_std == 0.0


def test_rolling_welford_matches_windowed_numpy() -> None:
    rng = np.random.default_rng(3)
    xs = rng.uniform(1.0, 50.0, size=80)
    window = 15
    rolling = RollingWelford(window)
    for i, x in enumerate(xs):
        stats = rolling.update(float(x))
        chunk = xs[max(0, i + 1 - window) : i + 1]
        np.testing.assert_allclose(stats.mean, chunk.mean(), rtol=1e-10, atol=1e-10)
        expected_std = 0.0 if chunk.size < 2 else float(chunk.std(ddof=1))
        np.testing.assert_allclose(stats.sample_std, expected_std, rtol=1e-9, atol=1e-9)


def test_log_volume_zscore_known_values() -> None:
    hist = [math.e**2 - 1.0] * 20  # log1p == 2
    # current log1p == 5 → z = (5-2)/0 → saturated
    z = log_volume_zscore(math.e**5 - 1.0, hist)
    assert z == MAX_Z


def test_log_volume_zscore_zero_variance_equal_volume() -> None:
    hist = [1_000_000.0] * 30
    z = log_volume_zscore(1_000_000.0, hist)
    assert z == 0.0
    assert math.isfinite(z)


def test_log_volume_zscore_zero_variance_spike_is_finite() -> None:
    hist = [1_000_000.0] * 30
    z = log_volume_zscore(2.8 * 1_000_000.0, hist)
    assert z == MAX_Z
    assert math.isfinite(z)


def test_log_volume_zscore_zero_current_volume() -> None:
    hist = [100.0, 110.0, 90.0, 105.0]
    z = log_volume_zscore(0.0, hist)
    assert math.isfinite(z)
    assert abs(z) <= MAX_Z


def test_price_zscore_zero_return_variance() -> None:
    prices = [100.0] * 25
    z = volatility_adjusted_price_zscore(100.0, 100.0, prices)
    assert z == 0.0


def test_price_zscore_gap_against_flat_history_saturates() -> None:
    prices = [100.0] * 25
    z = volatility_adjusted_price_zscore(94.0, 100.0, prices)
    assert z == -MAX_Z


def test_price_zscore_matches_manual_return_sigma() -> None:
    prices = [100.0, 101.0, 99.5, 100.5, 102.0, 101.2]
    log_rets = np.diff(np.log(np.array(prices)))
    price, prev = 103.0, 101.2
    current = math.log(price / prev)
    expected = (current - log_rets.mean()) / log_rets.std(ddof=1)
    z = volatility_adjusted_price_zscore(price, prev, prices)
    np.testing.assert_allclose(z, expected, rtol=1e-10, atol=1e-10)


def test_sector_relative_delta() -> None:
    # stock -2%, sector +1% → -0.03
    delta = sector_relative_delta(98.0, 100.0, 101.0, 100.0)
    np.testing.assert_allclose(delta, -0.03, atol=1e-12)


def test_mci_is_strictly_bounded() -> None:
    for raw_z_v, raw_z_p, rel in (
        (0.0, 0.0, 0.0),
        (MAX_Z, MAX_Z, 0.5),
        (-MAX_Z, -MAX_Z, -0.5),
        (1.2, -0.4, 0.01),
    ):
        score = _normalize_mci(raw_z_v, raw_z_p, rel)
        assert 0.0 <= score <= 100.0


def test_priority_boundaries() -> None:
    assert _priority_for(100.0) is Priority.CRITICAL
    assert _priority_for(75.0) is Priority.CRITICAL
    assert _priority_for(74.999) is Priority.MEDIUM
    assert _priority_for(50.0) is Priority.MEDIUM
    assert _priority_for(49.999) is Priority.LOW
    assert _priority_for(0.0) is Priority.LOW


def test_compute_mci_quiet_tape_is_low() -> None:
    volumes = [1_000_000 + i * 100 for i in range(40)]
    prices = [100.0 + 0.05 * math.sin(i / 3) for i in range(40)]
    result = compute_mci_score(
        volume=1_002_000,
        historical_volumes=volumes,
        price=prices[-1] * 1.0002,
        previous_price=prices[-1],
        historical_prices=prices,
        sector_price=1000.2,
        previous_sector_price=1000.0,
    )
    assert 0.0 <= result.mci <= 100.0
    assert result.priority is Priority.LOW
    assert math.isfinite(result.z_volume)
    assert math.isfinite(result.z_price)


def test_compute_mci_volume_spike_and_gap_are_critical() -> None:
    volumes = [1_000_000.0] * 50
    prices = [100.0] * 50
    result = compute_mci_score(
        volume=2.8 * 1_000_000.0,
        historical_volumes=volumes,
        price=93.0,
        previous_price=100.0,
        historical_prices=prices,
        sector_price=1000.0,
        previous_sector_price=1000.0,
    )
    assert result.z_volume == MAX_Z
    assert result.z_price == -MAX_Z
    assert result.mci >= 75
    assert result.priority is Priority.CRITICAL
    assert 0.0 <= result.mci <= 100.0


def test_empty_history_does_not_nan() -> None:
    result = compute_mci_score(
        volume=0.0,
        historical_volumes=[],
        price=0.0,
        previous_price=0.0,
        historical_prices=[],
        sector_price=0.0,
        previous_sector_price=0.0,
    )
    assert result.z_volume == 0.0
    assert result.z_price == 0.0
    assert result.mci == 0.0
    assert result.priority is Priority.LOW


def test_universe_has_fifteen_indian_names() -> None:
    symbols = [row["symbol"] for row in UNIVERSE]
    assert len(symbols) == 15
    assert len(set(symbols)) == 15
    for required in ("INFY", "TATAMOTORS", "HDFCBANK", "RELIANCE", "TCS"):
        assert required in symbols


def test_mock_feed_volume_spike_multiplier() -> None:
    quiet_feed = MockMarketFeed(seed=1)
    spike_feed = MockMarketFeed(seed=1)
    spike_feed.trigger_volume_spike("RELIANCE", ticks=1)
    quiet = {tick["symbol"]: tick for tick in quiet_feed.next_ticks()}
    spiked = {tick["symbol"]: tick for tick in spike_feed.next_ticks()}
    assert spiked["RELIANCE"]["volume"] == int(
        round(quiet["RELIANCE"]["volume"] * VOLUME_SPIKE_MULTIPLIER)
    )
    assert spiked["RELIANCE"]["anomaly"] == "volume_spike"
    assert quiet["RELIANCE"]["anomaly"] is None


def test_mock_feed_earnings_gap_down() -> None:
    feed = MockMarketFeed(seed=2)
    feed.trigger_earnings_gap_down("TCS", gap=-0.07)
    ticks = {tick["symbol"]: tick for tick in feed.next_ticks()}
    tcs = ticks["TCS"]
    move = tcs["price"] / tcs["previous_price"] - 1.0
    assert move < -0.05
    assert tcs["anomaly"] == "earnings_gap_down"
