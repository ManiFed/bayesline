"""Step 1: Compute market-level signals (internal, never shown to users).

For each market m mapped to a topic, over a time window W, compute:
- Attention: volume, open interest, depth
- Information arrival: price change, jump score, volatility
- Time sensitivity: time-to-resolution factor
- Quality controls: quality score, robustness score
- Composites: activity (A_m) and final signal (S_m)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import structlog

from ..config import settings
from ..models.market import Market, MarketSnapshot, MarketSignals
from ..services.store import DataStore

logger = structlog.get_logger()


class MarketSignalComputer:
    """Computes normalized market-level signals per the ImpactScore spec."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        # Running percentile trackers for robust normalization
        self._volume_values: list[float] = []
        self._oi_values: list[float] = []
        self._depth_values: list[float] = []
        self._price_change_values: list[float] = []
        self._jump_values: list[float] = []

    def compute(
        self, market: Market, window_hours: int = 24
    ) -> MarketSignals:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=window_hours)
        snapshots = self.store.get_snapshots(market.id, since=since)

        signals = MarketSignals(market_id=market.id, window_hours=window_hours)

        # ── Raw values ───────────────────────────────────────────────────
        volume = market.volume_usd
        oi = market.open_interest_usd
        liquidity = market.liquidity_usd

        # Price change and jump from snapshots
        price_change = 0.0
        jump = 0.0
        volatility = 0.0
        if len(snapshots) >= 2:
            probs = [s.probability for s in snapshots if s.probability is not None]
            if len(probs) >= 2:
                price_change = abs(probs[-1] - probs[0])
                diffs = [abs(probs[i+1] - probs[i]) for i in range(len(probs)-1)]
                jump = max(diffs) if diffs else 0.0
                volatility = float(np.std(probs)) if len(probs) > 1 else 0.0

        # Depth proxy: inverse of spread (lower spread = more depth)
        depth_raw = 0.0
        if snapshots:
            last = snapshots[-1]
            if last.spread is not None and last.spread > 0:
                depth_raw = 1.0 / last.spread
            elif liquidity > 0:
                depth_raw = math.log1p(liquidity)

        # ── Track for percentile normalization ───────────────────────────
        self._volume_values.append(volume)
        self._oi_values.append(oi)
        self._depth_values.append(depth_raw)
        self._price_change_values.append(price_change)
        self._jump_values.append(jump)

        # ── Normalize to [0, 1] via log + percentile rank ───────────────
        signals.volume_norm = self._lognorm(volume, self._volume_values)
        signals.open_interest_norm = self._lognorm(oi, self._oi_values)
        signals.depth_norm = self._percentile_rank(depth_raw, self._depth_values)
        signals.price_change = self._percentile_rank(price_change, self._price_change_values)
        signals.jump_score = self._percentile_rank(jump, self._jump_values)
        signals.realized_volatility = min(volatility * 10, 1.0)  # simple scale

        # ── Time sensitivity ─────────────────────────────────────────────
        signals.time_to_resolution = self._time_sensitivity(market, now)

        # ── Quality controls ─────────────────────────────────────────────
        signals.quality_score = self._quality(market)
        signals.robustness_score = self._robustness(market, snapshots)

        # ── Composites ───────────────────────────────────────────────────
        # A_m = 0.35 * lognorm(V) + 0.25 * lognorm(O) + 0.15 * D + 0.15 * ΔP + 0.10 * J
        w = settings
        signals.activity_composite = (
            w.volume_weight * signals.volume_norm
            + w.open_interest_weight * signals.open_interest_norm
            + w.depth_weight * signals.depth_norm
            + w.price_change_weight * signals.price_change
            + w.jump_weight * signals.jump_score
        )

        # S_m = A_m * (0.6 * Q_m + 0.4 * R_m)
        quality_factor = (
            w.quality_weight * signals.quality_score
            + w.robustness_weight * signals.robustness_score
        )
        signals.market_signal = signals.activity_composite * quality_factor

        signals.computed_at = now
        return signals

    def compute_all(self, window_hours: int = 24) -> dict[str, MarketSignals]:
        """Compute signals for all active markets."""
        results: dict[str, MarketSignals] = {}
        for market in self.store.get_all_markets():
            if market.status.value != "active":
                continue
            results[market.id] = self.compute(market, window_hours)
        return results

    # ── Normalization helpers ────────────────────────────────────────────

    @staticmethod
    def _lognorm(value: float, population: list[float]) -> float:
        """Log-transform then percentile-rank within the population."""
        if value <= 0:
            return 0.0
        log_val = math.log1p(value)
        log_pop = sorted(math.log1p(max(v, 0)) for v in population)
        if not log_pop:
            return 0.0
        rank = sum(1 for v in log_pop if v <= log_val)
        return rank / len(log_pop)

    @staticmethod
    def _percentile_rank(value: float, population: list[float]) -> float:
        if not population:
            return 0.0
        sorted_pop = sorted(population)
        rank = sum(1 for v in sorted_pop if v <= value)
        return rank / len(sorted_pop)

    @staticmethod
    def _time_sensitivity(market: Market, now: datetime) -> float:
        """Peaks when resolution is near, decays when far away."""
        if not market.close_date:
            return 0.3  # unknown resolution = moderate
        delta = (market.close_date - now).total_seconds()
        if delta <= 0:
            return 0.1  # already past
        days = delta / 86400
        if days <= 1:
            return 1.0
        if days <= 7:
            return 0.8
        if days <= 30:
            return 0.5
        if days <= 90:
            return 0.3
        return 0.1

    @staticmethod
    def _quality(market: Market) -> float:
        """Q_m: clarity of resolution, dispute rate, edit stability."""
        score = 0.5
        if market.has_clear_resolution:
            score += 0.2
        if market.resolution_source:
            score += 0.1
        # Penalize many edits or disputes
        if market.edit_count > 5:
            score -= 0.15
        if market.dispute_count > 0:
            score -= 0.1 * min(market.dispute_count, 3)
        return max(0.0, min(1.0, score))

    @staticmethod
    def _robustness(market: Market, snapshots: list[MarketSnapshot]) -> float:
        """R_m: sustained volume, many traders, cross-venue potential."""
        score = 0.3
        if market.num_traders > 100:
            score += 0.3
        elif market.num_traders > 20:
            score += 0.15

        # Sustained volume: check if we have consistent snapshot activity
        if len(snapshots) >= 5:
            volumes = [s.volume_usd for s in snapshots]
            nonzero = sum(1 for v in volumes if v > 0)
            if nonzero / len(volumes) > 0.8:
                score += 0.2

        if market.liquidity_usd > 10000:
            score += 0.2
        elif market.liquidity_usd > 1000:
            score += 0.1

        return max(0.0, min(1.0, score))
