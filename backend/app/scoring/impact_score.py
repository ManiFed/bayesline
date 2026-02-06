"""Step 5: Final ImpactScore computation and feed explanation generation.

ImpactScore(t) =
  0.45 * MarketSignal(t)
  + 0.20 * CoverageGap(t)
  + 0.20 * ExpectedConsequence(t)
  + 0.10 * TimeSensitivity(t)
  - 0.15 * ManipulationRisk(t)
  - 0.10 * HypeGap(t)

Clamped to [0, 100]. Explanation generated without mentioning markets.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from ..config import settings
from ..models.market import MarketSignals
from ..models.topic import ImpactTopic, TopicScores
from ..services.store import DataStore
from .market_signals import MarketSignalComputer
from .news_coverage import NewsCoverageScorer
from .consequence import ConsequenceScorer

logger = structlog.get_logger()


class ImpactScorer:
    """Orchestrates the full ImpactScore pipeline for all topics."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self.market_computer = MarketSignalComputer(store)
        self.coverage_scorer = NewsCoverageScorer(store)
        self.consequence_scorer = ConsequenceScorer(store)

    def score_topic(self, topic: ImpactTopic) -> TopicScores:
        """Compute all scores for a single topic."""
        # Step 1 + 2: Aggregate market signals
        market_signal = self._aggregate_market_signal(topic)

        # Step 3: Coverage gaps
        coverage_gap, hype_gap = self.coverage_scorer.compute_gaps(
            topic, market_signal
        )
        news_coverage = self.coverage_scorer.compute(topic)

        # Step 4: Consequence
        consequence = self.consequence_scorer.compute(topic)

        # Time sensitivity (aggregate from mapped markets)
        time_sensitivity = self._aggregate_time_sensitivity(topic)

        # Manipulation risk
        manipulation_risk = self._manipulation_risk(topic)

        # Step 5: Final score
        raw = (
            settings.market_signal_weight * market_signal
            + settings.coverage_gap_weight * coverage_gap
            + settings.consequence_weight * consequence
            + settings.time_sensitivity_weight * time_sensitivity
            - settings.manipulation_risk_penalty * manipulation_risk
            - settings.hype_gap_penalty * hype_gap
        )
        impact_score = max(0.0, min(100.0, raw * 100))

        # Generate explanation
        explanation, drivers = self._explain(
            market_signal, coverage_gap, hype_gap,
            consequence, time_sensitivity, manipulation_risk,
            impact_score,
        )

        return TopicScores(
            market_signal=market_signal,
            news_coverage=news_coverage,
            coverage_gap=coverage_gap,
            hype_gap=hype_gap,
            expected_consequence=consequence,
            time_sensitivity=time_sensitivity,
            manipulation_risk=manipulation_risk,
            impact_score=impact_score,
            explanation=explanation,
            explanation_drivers=drivers,
            computed_at=datetime.now(timezone.utc),
        )

    def score_all_topics(self) -> dict[str, TopicScores]:
        """Score every topic in the store."""
        # Pre-compute all market signals
        self.market_computer.compute_all()

        results: dict[str, TopicScores] = {}
        for topic in self.store.get_all_topics():
            scores = self.score_topic(topic)
            topic.scores = scores
            self.store.upsert_topic(topic)
            results[topic.id] = scores
        return results

    def _aggregate_market_signal(self, topic: ImpactTopic) -> float:
        """Step 2: Capped weighted sum of S_m across mapped markets."""
        mappings = self.store.get_topic_market_mappings(topic.id)
        if not mappings:
            # Fallback: use market_ids directly
            mappings_lite = [
                (mid, 1.0) for mid in topic.market_ids
            ]
        else:
            mappings_lite = [
                (m.market_id, m.relevance_weight) for m in mappings
            ]

        total = 0.0
        for market_id, weight in mappings_lite:
            market = self.store.get_market(market_id)
            if not market:
                continue
            signals = self.market_computer.compute(market)
            total += weight * signals.market_signal

        # Cap to prevent single-market dominance
        return min(total, 1.0)

    def _aggregate_time_sensitivity(self, topic: ImpactTopic) -> float:
        """Aggregate T_m across mapped markets and known deadlines."""
        t_values: list[float] = []

        for mid in topic.market_ids:
            market = self.store.get_market(mid)
            if market:
                signals = self.market_computer.compute(market)
                t_values.append(signals.time_to_resolution)

        # Also consider explicit deadlines
        now = datetime.now(timezone.utc)
        for dl in topic.deadlines:
            delta_days = (dl.date - now).total_seconds() / 86400
            if delta_days <= 0:
                t_values.append(0.1)
            elif delta_days <= 1:
                t_values.append(1.0)
            elif delta_days <= 7:
                t_values.append(0.8)
            elif delta_days <= 30:
                t_values.append(0.5)
            else:
                t_values.append(0.2)

        return max(t_values) if t_values else 0.3

    def _manipulation_risk(self, topic: ImpactTopic) -> float:
        """ManipulationRisk(t): thin liquidity, spikes, single-venue, edits."""
        risk_factors: list[float] = []

        markets = [self.store.get_market(mid) for mid in topic.market_ids]
        markets = [m for m in markets if m is not None]

        if not markets:
            return 0.3  # Unknown = moderate risk

        # Single venue
        venues = set(m.venue for m in markets)
        if len(venues) == 1:
            risk_factors.append(0.4)

        # Thin liquidity (average)
        avg_liq = sum(m.liquidity_usd for m in markets) / len(markets)
        if avg_liq < 1000:
            risk_factors.append(0.5)
        elif avg_liq < 10000:
            risk_factors.append(0.2)

        # Few traders
        avg_traders = sum(m.num_traders for m in markets) / len(markets)
        if avg_traders < 10:
            risk_factors.append(0.5)
        elif avg_traders < 50:
            risk_factors.append(0.2)

        # Excessive edits
        total_edits = sum(m.edit_count for m in markets)
        if total_edits > 10:
            risk_factors.append(0.3)

        return sum(risk_factors) / max(len(risk_factors), 1)

    @staticmethod
    def _explain(
        market_signal: float,
        coverage_gap: float,
        hype_gap: float,
        consequence: float,
        time_sensitivity: float,
        manipulation_risk: float,
        impact_score: float,
    ) -> tuple[str, list[str]]:
        """Generate a user-facing explanation without mentioning markets."""
        drivers: list[str] = []

        if market_signal > 0.6:
            drivers.append("High activity from informed sources")
        elif market_signal > 0.3:
            drivers.append("Moderate attention from informed sources")

        if coverage_gap > 0.3:
            drivers.append("Undercovered relative to its significance")

        if consequence > 0.7:
            drivers.append("High potential real-world impact")
        elif consequence > 0.4:
            drivers.append("Meaningful potential consequences")

        if time_sensitivity > 0.7:
            drivers.append("Important deadline approaching")

        if hype_gap > 0.3:
            drivers.append("Coverage may exceed actual significance")

        if not drivers:
            drivers.append("Tracked due to emerging signals")

        explanation = ". ".join(drivers[:3]) + "."
        return explanation, drivers
