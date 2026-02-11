"""Tests for the ImpactScore scoring pipeline."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.market import Market, MarketSnapshot, MarketVenue, MarketStatus
from app.models.topic import ImpactTopic, Deadline
from app.models.news import NewsArticle
from app.models.entity import Entity, EntityType
from app.services.store import DataStore
from app.scoring.market_signals import MarketSignalComputer
from app.scoring.news_coverage import NewsCoverageScorer
from app.scoring.consequence import ConsequenceScorer
from app.scoring.impact_score import ImpactScorer


def _make_market(
    mid: str = "test:m1",
    volume: float = 10000,
    oi: float = 5000,
    prob: float = 0.65,
    liquidity: float = 8000,
    traders: int = 50,
    close_days: int = 7,
) -> Market:
    now = datetime.now(timezone.utc)
    return Market(
        id=mid,
        venue=MarketVenue.POLYMARKET,
        venue_id=mid,
        question="Will X happen by end of year?",
        created_at=now - timedelta(days=30),
        close_date=now + timedelta(days=close_days),
        status=MarketStatus.ACTIVE,
        current_probability=prob,
        volume_usd=volume,
        open_interest_usd=oi,
        num_traders=traders,
        liquidity_usd=liquidity,
    )


def _make_snapshots(
    market_id: str, n: int = 10, base_prob: float = 0.5
) -> list[MarketSnapshot]:
    now = datetime.now(timezone.utc)
    snaps = []
    for i in range(n):
        snaps.append(MarketSnapshot(
            market_id=market_id,
            timestamp=now - timedelta(hours=n - i),
            probability=base_prob + (i * 0.02),
            volume_usd=1000 + i * 100,
        ))
    return snaps


def _attach_recent_article(store: DataStore, topic: ImpactTopic, aid: str = "a1") -> None:
    article = NewsArticle(
        id=aid,
        url=f"https://example.com/{aid}",
        title=f"Report for {topic.title}",
        source_name="Reuters",
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    store.upsert_article(article)
    topic.article_ids = [aid]
    topic.approved_story_cluster = True


class TestMarketSignalComputer:
    def test_compute_basic(self):
        store = DataStore()
        market = _make_market()
        store.upsert_market(market)
        for snap in _make_snapshots(market.id):
            store.append_snapshot(snap)

        computer = MarketSignalComputer(store)
        signals = computer.compute(market)

        assert 0 <= signals.volume_norm <= 1
        assert 0 <= signals.activity_composite <= 1
        assert 0 <= signals.market_signal <= 1
        assert 0 <= signals.quality_score <= 1
        assert 0 <= signals.robustness_score <= 1

    def test_high_volume_scores_higher(self):
        store = DataStore()
        low = _make_market("test:low", volume=100, oi=50, liquidity=100, traders=5)
        high = _make_market("test:high", volume=1_000_000, oi=500_000, liquidity=100_000, traders=500)
        store.upsert_market(low)
        store.upsert_market(high)
        for snap in _make_snapshots(low.id):
            store.append_snapshot(snap)
        for snap in _make_snapshots(high.id):
            store.append_snapshot(snap)

        computer = MarketSignalComputer(store)
        sig_low = computer.compute(low)
        sig_high = computer.compute(high)

        assert sig_high.activity_composite >= sig_low.activity_composite

    def test_time_sensitivity_peaks_near_close(self):
        store = DataStore()
        near = _make_market("test:near", close_days=1)
        far = _make_market("test:far", close_days=365)
        store.upsert_market(near)
        store.upsert_market(far)

        computer = MarketSignalComputer(store)
        sig_near = computer.compute(near)
        sig_far = computer.compute(far)

        assert sig_near.time_to_resolution > sig_far.time_to_resolution


class TestConsequenceScorer:
    def test_war_category_scores_high(self):
        store = DataStore()
        topic = ImpactTopic(
            id="t1",
            title="Russia-Ukraine conflict escalation",
            category="war",
        )
        store.upsert_topic(topic)
        scorer = ConsequenceScorer(store)
        score = scorer.compute(topic)
        assert score >= 0.7

    def test_entertainment_scores_low(self):
        store = DataStore()
        topic = ImpactTopic(
            id="t2",
            title="Celebrity awards show results",
            category="entertainment",
        )
        store.upsert_topic(topic)
        scorer = ConsequenceScorer(store)
        score = scorer.compute(topic)
        assert score < 0.5

    def test_population_scale_boosts_score(self):
        store = DataStore()
        entity = Entity(
            id="e1",
            entity_type=EntityType.COUNTRY,
            name="United States",
            population_affected=330_000_000,
        )
        store.upsert_entity(entity)
        topic = ImpactTopic(
            id="t3",
            title="Government shutdown",
            category="government",
            entity_ids=["e1"],
        )
        store.upsert_topic(topic)
        scorer = ConsequenceScorer(store)
        score = scorer.compute(topic)
        assert score >= 0.6


class TestImpactScorer:
    def test_full_pipeline(self):
        store = DataStore()

        # Set up market
        market = _make_market()
        store.upsert_market(market)
        for snap in _make_snapshots(market.id):
            store.append_snapshot(snap)

        # Set up topic
        topic = ImpactTopic(
            id="t1",
            title="Government shutdown deadline",
            category="government",
            market_ids=[market.id],
        )
        _attach_recent_article(store, topic)
        store.upsert_topic(topic)

        scorer = ImpactScorer(store)
        scores = scorer.score_topic(topic)

        assert 0 <= scores.impact_score <= 100
        assert scores.explanation != ""
        assert len(scores.explanation_drivers) > 0

    def test_score_all_topics(self):
        store = DataStore()

        for i in range(3):
            market = _make_market(f"test:m{i}", volume=1000 * (i + 1))
            store.upsert_market(market)
            topic = ImpactTopic(
                id=f"t{i}",
                title=f"Topic {i}",
                category="politics",
                market_ids=[market.id],
            )
            _attach_recent_article(store, topic, aid=f"a{i}")
            store.upsert_topic(topic)

        scorer = ImpactScorer(store)
        results = scorer.score_all_topics()

        assert len(results) == 3
        for scores in results.values():
            assert 0 <= scores.impact_score <= 100


class TestNewsCoverageScorer:
    def test_no_articles_returns_zero(self):
        store = DataStore()
        topic = ImpactTopic(id="t1", title="Something obscure")
        store.upsert_topic(topic)

        scorer = NewsCoverageScorer(store)
        score = scorer.compute(topic)
        assert score == 0.0

    def test_coverage_gap_detection(self):
        store = DataStore()
        topic = ImpactTopic(id="t1", title="Obscure but important")
        store.upsert_topic(topic)

        scorer = NewsCoverageScorer(store)
        gap, hype = scorer.compute_gaps(topic, market_signal=0.8)

        assert gap > 0  # Market cares, no news coverage
        assert hype == 0.0
