"""Final ImpactScore v2 with story/market layering and public eligibility gating."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import settings
from ..models.topic import ImpactTopic, TopicScores, MarketReactionEvent
from ..services.store import DataStore
from .market_signals import MarketSignalComputer
from .news_coverage import NewsCoverageScorer
from .consequence import ConsequenceScorer


_ALLOWED_DOMAINS = {
    "government", "geopolitics", "war", "regulation", "finance",
    "economy", "legal", "technology", "health",
}

_TRIVIAL_TAXONOMY_PENALTY = {
    "novelty_gambling": 0.9,
    "sports_outcome": 0.8,
    "lottery": 0.95,
    "coin_flip": 0.95,
    "political_macro": 0.0,
    "corporate_regulatory": 0.0,
    "financial_instrument_price": 0.0,
}


class ImpactScorer:
    def __init__(self, store: DataStore) -> None:
        self.store = store
        self.market_computer = MarketSignalComputer(store)
        self.coverage_scorer = NewsCoverageScorer(store)
        self.consequence_scorer = ConsequenceScorer(store)

    def score_topic(self, topic: ImpactTopic) -> TopicScores:
        if not self._is_publicly_eligible(topic):
            return TopicScores(
                impact_score=0.0,
                explanation="Filtered: story cluster lacks current approved reporting.",
                explanation_drivers=["Public eligibility gate"],
                public_eligibility_score=0.0,
            )

        story_quality = self._story_quality_score(topic)
        newsworthiness = self._newsworthiness_prior(topic)
        coverage_diversity = self._coverage_diversity_score(topic)
        story_layer_score = (story_quality * 0.35) + (newsworthiness * 0.4) + (coverage_diversity * 0.25)

        reaction_events = self._derive_reaction_events(topic)
        topic.reaction_events = reaction_events
        relevance = self._relevance_score(topic)
        reaction_evidence = self._reaction_evidence_score(reaction_events)
        cross_market = self._cross_market_confirmation(topic, reaction_events)
        mapping_confidence = self._story_market_mapping_confidence(topic)

        market_evidence_score = (
            relevance * 0.3
            + reaction_evidence * 0.4
            + cross_market * 0.3
        )

        coverage_gap, hype_gap = self.coverage_scorer.compute_gaps(topic, market_evidence_score)
        consequence = self.consequence_scorer.compute(topic)
        time_sensitivity = self._aggregate_time_sensitivity(topic)
        manipulation_risk = self._manipulation_risk(topic)

        narrative_coherence_boost, narrative_novelty_boost = self._narrative_boosts(topic, cross_market)
        triviality_penalty = self._market_triviality_penalty(topic)

        if mapping_confidence < settings.min_mapping_confidence:
            market_evidence_score *= 0.25

        layered_score = (
            settings.story_layer_weight * story_layer_score
            + settings.market_evidence_weight * market_evidence_score
        )

        raw = (
            layered_score
            + 0.15 * consequence
            + 0.1 * time_sensitivity
            + 0.08 * coverage_gap
            + narrative_coherence_boost
            + narrative_novelty_boost
            - 0.1 * hype_gap
            - 0.18 * manipulation_risk
            - settings.novelty_penalty_weight * triviality_penalty
        )
        impact_score = max(0.0, min(100.0, raw * 100))

        explanation, drivers = self._explain(story_layer_score, market_evidence_score, reaction_evidence, cross_market, triviality_penalty, mapping_confidence)

        return TopicScores(
            market_signal=market_evidence_score,
            news_coverage=self.coverage_scorer.compute(topic),
            coverage_gap=coverage_gap,
            hype_gap=hype_gap,
            expected_consequence=consequence,
            time_sensitivity=time_sensitivity,
            manipulation_risk=manipulation_risk,
            story_layer_score=story_layer_score,
            market_evidence_score=market_evidence_score,
            public_eligibility_score=1.0,
            story_market_mapping_confidence=mapping_confidence,
            market_triviality_penalty=triviality_penalty,
            narrative_coherence_boost=narrative_coherence_boost,
            narrative_novelty_boost=narrative_novelty_boost,
            impact_score=impact_score,
            explanation=explanation,
            explanation_drivers=drivers,
            computed_at=datetime.now(timezone.utc),
        )

    def score_all_topics(self) -> dict[str, TopicScores]:
        self.market_computer.compute_all()
        results: dict[str, TopicScores] = {}
        for topic in self.store.get_all_topics():
            topic.eligible_for_homepage = self._is_publicly_eligible(topic)
            scores = self.score_topic(topic)
            topic.scores = scores
            self.store.upsert_topic(topic)
            results[topic.id] = scores
        return results

    def _is_publicly_eligible(self, topic: ImpactTopic) -> bool:
        if not topic.approved_story_cluster:
            return False
        if not topic.article_ids:
            return False
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.homepage_recency_hours)
        has_recent = False
        for aid in topic.article_ids:
            article = self.store.get_article(aid)
            if article and article.published_at and article.published_at >= recent_cutoff:
                has_recent = True
                break
        if not has_recent:
            return False
        if topic.market_taxonomy in {"coin_flip", "lottery"} and topic.category not in {"regulation", "legal"}:
            return False
        return True

    def _story_quality_score(self, topic: ImpactTopic) -> float:
        cluster_density = min(len(topic.article_ids) / 6, 1.0)
        entity_consistency = min(len(set(topic.entity_ids)) / max(len(topic.entity_ids), 1), 1.0)
        citation_ratio = min(len(topic.citations) / max(len(topic.article_ids), 1), 1.0)
        return (cluster_density * 0.4) + (entity_consistency * 0.3) + (citation_ratio * 0.3)

    def _newsworthiness_prior(self, topic: ImpactTopic) -> float:
        category = topic.category.lower()
        if category in _ALLOWED_DOMAINS:
            return 0.75
        if category in {"sports", "entertainment"}:
            return 0.15
        return 0.45

    def _coverage_diversity_score(self, topic: ImpactTopic) -> float:
        outlets: set[str] = set()
        source_types: set[str] = set()
        for aid in topic.article_ids:
            article = self.store.get_article(aid)
            if not article:
                continue
            if article.source_name:
                outlets.add(article.source_name.lower())
            source_types.add(article.source_type.value)
        return min((len(outlets) * 0.7 + len(source_types) * 0.3) / 8, 1.0)

    def _relevance_score(self, topic: ImpactTopic) -> float:
        mappings = self.store.get_topic_market_mappings(topic.id)
        if not mappings:
            return 0.0
        return min(sum(m.relevance_weight for m in mappings) / len(mappings), 1.0)

    def _derive_reaction_events(self, topic: ImpactTopic) -> list[MarketReactionEvent]:
        events: list[MarketReactionEvent] = []
        if not topic.article_ids:
            return events
        article_times = [self.store.get_article(aid).published_at for aid in topic.article_ids if self.store.get_article(aid) and self.store.get_article(aid).published_at]
        if not article_times:
            return events
        first_story_time = min(article_times)
        for market_id in topic.market_ids:
            snaps = sorted(self.store.get_snapshots(market_id), key=lambda s: s.timestamp)
            if len(snaps) < 3:
                continue
            before = [s for s in snaps if s.timestamp < first_story_time]
            after = [s for s in snaps if s.timestamp >= first_story_time]
            if len(after) < 2:
                continue
            baseline = before[-1].probability if before and before[-1].probability is not None else after[0].probability
            if baseline is None:
                continue
            move_series = [(s.timestamp, abs((s.probability or baseline) - baseline)) for s in after if s.probability is not None]
            if not move_series:
                continue
            peak_time, peak = max(move_series, key=lambda x: x[1])
            reaction_start = next((ts for ts, delta in move_series if delta > 0.03), after[0].timestamp)
            end_move = move_series[-1][1]
            reversal = max(peak - end_move, 0.0)
            persistence = max((move_series[-1][0] - peak_time).total_seconds() / 60, 0.0)
            pre_move = 0.0
            if len(before) >= 2 and before[0].probability is not None and before[-1].probability is not None:
                pre_move = abs(before[-1].probability - before[0].probability)
            implied_surprise = peak / max(0.01, float(self.market_computer.compute(self.store.get_market(market_id)).realized_volatility))
            events.append(MarketReactionEvent(
                market_id=market_id,
                reaction_start_time=reaction_start,
                peak_move_time=peak_time,
                peak_magnitude=min(peak, 1.0),
                persistence_minutes=persistence,
                reversal_magnitude=min(reversal, 1.0),
                implied_surprise=min(implied_surprise / 5, 1.0),
                moved_pre_story=pre_move > 0.05,
                confirmed=persistence >= 30 and peak > 0.03,
            ))
        return events

    def _reaction_evidence_score(self, events: list[MarketReactionEvent]) -> float:
        if not events:
            return 0.0
        vals = []
        for ev in events:
            score = ev.peak_magnitude * 0.45 + min(ev.persistence_minutes / 90, 1.0) * 0.35 + ev.implied_surprise * 0.2
            if ev.moved_pre_story:
                score *= 0.6
            vals.append(score)
        return min(sum(vals) / len(vals), 1.0)

    def _cross_market_confirmation(self, topic: ImpactTopic, events: list[MarketReactionEvent]) -> float:
        if not events:
            return 0.0
        domains: set[str] = set()
        for market_id in {e.market_id for e in events if e.confirmed}:
            market = self.store.get_market(market_id)
            if market:
                domains.add(f"prediction:{market.venue.value}")
                cat = market.category.lower()
                if any(k in cat for k in ["stock", "equity"]):
                    domains.add("equities")
                if any(k in cat for k in ["fx", "currency"]):
                    domains.add("fx")
                if any(k in cat for k in ["oil", "commodity", "gold"]):
                    domains.add("commodities")
                if "crypto" in cat:
                    domains.add("crypto")
        return min(len(domains) / 4, 1.0)

    def _story_market_mapping_confidence(self, topic: ImpactTopic) -> float:
        mappings = self.store.get_topic_market_mappings(topic.id)
        if not mappings:
            return 0.0
        weights = [m.relevance_weight for m in mappings]
        entity_strength = min(len(topic.entity_ids) / 4, 1.0)
        disambiguation = 1.0 if len(set(topic.entity_ids)) >= max(1, len(topic.entity_ids) * 0.7) else 0.5
        return min((sum(weights) / len(weights)) * 0.5 + entity_strength * 0.3 + disambiguation * 0.2, 1.0)

    def _aggregate_time_sensitivity(self, topic: ImpactTopic) -> float:
        values: list[float] = []
        for market_id in topic.market_ids:
            market = self.store.get_market(market_id)
            if market:
                values.append(self.market_computer.compute(market).time_to_resolution)
        return max(values) if values else 0.3

    def _manipulation_risk(self, topic: ImpactTopic) -> float:
        markets = [self.store.get_market(mid) for mid in topic.market_ids]
        markets = [m for m in markets if m is not None]
        if not markets:
            return 0.5
        avg_liq = sum(m.liquidity_usd for m in markets) / len(markets)
        depth_component = min(avg_liq / 25000, 1.0)
        average_volume = sum(m.volume_usd for m in markets) / len(markets)
        volume_component = min(average_volume / 50000, 1.0)
        venue_reliability = sum(self._venue_reliability(m.venue.value) for m in markets) / len(markets)
        informational_weight = 0.45 * depth_component + 0.35 * volume_component + 0.2 * venue_reliability
        return 1 - informational_weight

    def _market_triviality_penalty(self, topic: ImpactTopic) -> float:
        penalty = _TRIVIAL_TAXONOMY_PENALTY.get(topic.market_taxonomy, 0.0)
        if topic.category in {"regulation", "legal"}:
            return penalty * 0.15
        return penalty

    def _narrative_boosts(self, topic: ImpactTopic, cross_market_score: float) -> tuple[float, float]:
        coherence = 0.06 if topic.narrative_id else 0.0
        novelty = 0.05 if topic.narrative_id and topic.narrative_label.lower().startswith("emerging") and cross_market_score > 0.35 else 0.0
        return coherence, novelty

    @staticmethod
    def _venue_reliability(venue: str) -> float:
        return {
            "kalshi": 0.85,
            "polymarket": 0.72,
            "manifold": 0.6,
            "metaculus": 0.65,
        }.get(venue, 0.55)

    @staticmethod
    def _explain(
        story_layer_score: float,
        market_evidence_score: float,
        reaction_evidence: float,
        cross_market: float,
        triviality_penalty: float,
        mapping_confidence: float,
    ) -> tuple[str, list[str]]:
        drivers: list[str] = []
        if story_layer_score > 0.6:
            drivers.append("Strong, coherent reporting cluster")
        if reaction_evidence > 0.5:
            drivers.append("Post-publication market reaction persisted")
        if cross_market > 0.35:
            drivers.append("Cross-domain market confirmation")
        if mapping_confidence < settings.min_mapping_confidence:
            drivers.append("Weak story-market mapping confidence")
        if triviality_penalty > 0.4:
            drivers.append("Triviality penalty applied")
        if not drivers:
            drivers.append("Moderate story importance with limited confirmation")
        return ". ".join(drivers[:3]) + ".", drivers
