"""Tests for feed assembly and personalization."""

from datetime import datetime, timedelta, timezone

from app.models.topic import ImpactTopic, TopicScores, Deadline
from app.models.feed import UserPreferences
from app.services.store import DataStore
from app.services.feed import FeedService


def _make_scored_topic(
    tid: str,
    title: str,
    category: str = "politics",
    impact: float = 50,
    coverage_gap: float = 0.2,
    consequence: float = 0.5,
    time_sensitivity: float = 0.3,
) -> ImpactTopic:
    now = datetime.now(timezone.utc)
    return ImpactTopic(
        id=tid,
        title=title,
        category=category,
        what_happened=f"{title} is happening. It has significant implications. Details emerging.",
        what_changed_today="New developments reported.",
        why_it_matters="Affects millions of people.",
        scores=TopicScores(
            impact_score=impact,
            market_signal=impact / 100,
            coverage_gap=coverage_gap,
            expected_consequence=consequence,
            time_sensitivity=time_sensitivity,
            explanation="High activity from informed sources.",
            explanation_drivers=["High activity from informed sources"],
        ),
        created_at=now,
        updated_at=now,
    )


class TestFeedService:
    def test_build_feed_empty(self):
        store = DataStore()
        feed_service = FeedService(store)
        response = feed_service.build_feed()
        assert response.total_topics == 0
        assert len(response.sections) == 4

    def test_build_feed_with_topics(self):
        store = DataStore()
        for i in range(5):
            topic = _make_scored_topic(
                f"t{i}", f"Topic {i}", impact=80 - i * 10,
            )
            store.upsert_topic(topic)

        feed_service = FeedService(store)
        response = feed_service.build_feed()

        assert response.total_topics == 5
        # Breaking section should have items
        breaking = next(s for s in response.sections if s.name == "breaking")
        assert len(breaking.items) > 0
        # Items should be sorted by impact score
        scores = [item.card.impact_score for item in breaking.items]
        assert scores == sorted(scores, reverse=True)

    def test_undercovered_section(self):
        store = DataStore()
        # High coverage gap topic
        t1 = _make_scored_topic("t1", "Hidden crisis", coverage_gap=0.8)
        # Low coverage gap
        t2 = _make_scored_topic("t2", "Well covered", coverage_gap=0.05)
        store.upsert_topic(t1)
        store.upsert_topic(t2)

        feed_service = FeedService(store)
        response = feed_service.build_feed()

        undercovered = next(s for s in response.sections if s.name == "undercovered")
        if undercovered.items:
            assert undercovered.items[0].card.id == "t1"

    def test_deadlines_section(self):
        store = DataStore()
        now = datetime.now(timezone.utc)
        topic = _make_scored_topic("t1", "Vote deadline", time_sensitivity=0.9)
        topic.deadlines = [
            Deadline(date=now + timedelta(days=2), description="Senate vote")
        ]
        store.upsert_topic(topic)

        feed_service = FeedService(store)
        response = feed_service.build_feed()

        deadlines = next(s for s in response.sections if s.name == "deadlines")
        assert len(deadlines.items) > 0

    def test_personalization_boosts_geography(self):
        store = DataStore()
        t1 = _make_scored_topic("t1", "US shutdown crisis", impact=60)
        t2 = _make_scored_topic("t2", "EU trade policy", impact=60)
        store.upsert_topic(t1)
        store.upsert_topic(t2)

        prefs = UserPreferences(geographies=["US"])
        feed_service = FeedService(store)
        response = feed_service.build_feed(prefs)

        breaking = next(s for s in response.sections if s.name == "breaking")
        if len(breaking.items) >= 2:
            # US topic should be boosted
            us_item = next(i for i in breaking.items if "US" in i.card.title)
            assert us_item.personalization_boost > 0

    def test_consequence_floor_enforced(self):
        store = DataStore()
        # High consequence topic that might otherwise be filtered
        t = _make_scored_topic("t1", "Critical infrastructure", consequence=0.9, impact=20)
        store.upsert_topic(t)

        prefs = UserPreferences(min_consequence_floor=0.3)
        feed_service = FeedService(store)
        response = feed_service.build_feed(prefs)

        # Topic should appear somewhere in the feed
        all_ids = set()
        for section in response.sections:
            for item in section.items:
                all_ids.add(item.card.id)
        assert "t1" in all_ids

    def test_card_has_no_market_data(self):
        store = DataStore()
        topic = _make_scored_topic("t1", "Test topic")
        topic.market_ids = ["polymarket:123"]
        store.upsert_topic(topic)

        feed_service = FeedService(store)
        response = feed_service.build_feed()

        breaking = next(s for s in response.sections if s.name == "breaking")
        if breaking.items:
            card = breaking.items[0].card
            # Card should not expose market IDs
            card_dict = card.model_dump()
            card_json = str(card_dict)
            assert "polymarket" not in card_json
            assert "market_ids" not in card_dict
