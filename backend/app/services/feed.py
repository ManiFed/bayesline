"""Feed assembly from eligible scored stories and narrative-aware sections."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..models.topic import ImpactTopic, TopicCard
from ..models.feed import FeedItem, FeedSection, FeedResponse, UserPreferences
from ..services.store import DataStore


class FeedService:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    def build_feed(
        self,
        preferences: Optional[UserPreferences] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> FeedResponse:
        prefs = preferences or UserPreferences()
        topics = [t for t in self.store.get_all_topics() if t.eligible_for_homepage]

        if not topics:
            return FeedResponse(sections=self._empty_sections(), total_topics=0, page=page, page_size=page_size)

        breaking = self._breaking_importance(topics)
        undercovered = self._undercovered(topics)
        slow_burn = self._slow_burn(topics)
        deadlines = self._upcoming_deadlines(topics)

        breaking = self._personalize(breaking, prefs)
        undercovered = self._personalize(undercovered, prefs)
        slow_burn = self._personalize(slow_burn, prefs)
        deadlines = self._personalize(deadlines, prefs)

        sections = [
            FeedSection(
                name="breaking",
                display_name="Breaking",
                description="Highest ImpactScore with confirmed post-publication reaction.",
                items=breaking[:page_size],
            ),
            FeedSection(
                name="undercovered",
                display_name="Undercovered",
                description="High impact with low coverage and strong cross-market confirmation.",
                items=undercovered[: page_size // 2],
            ),
            FeedSection(
                name="slow_burn",
                display_name="Slow Burn",
                description="Narratives whose cumulative impact has climbed steadily.",
                items=slow_burn[: page_size // 2],
            ),
            FeedSection(
                name="deadlines",
                display_name="Upcoming Deadlines",
                description="Near-term resolution dates tied to current reporting.",
                items=deadlines[: page_size // 2],
            ),
        ]

        return FeedResponse(sections=sections, total_topics=len(topics), page=page, page_size=page_size)

    def _breaking_importance(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        now = datetime.now(timezone.utc)
        candidates = [
            t for t in topics
            if (now - t.updated_at).total_seconds() <= 86400
            and any(e.confirmed for e in t.reaction_events)
        ]
        if not candidates:
            candidates = topics
        candidates.sort(key=lambda t: t.scores.impact_score, reverse=True)
        return [self._make_feed_item(t, "breaking", i) for i, t in enumerate(candidates)]

    def _undercovered(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        candidates = [
            t for t in topics
            if t.scores.coverage_gap > 0.15 and t.scores.market_evidence_score > 0.35
        ]
        candidates.sort(key=lambda t: t.scores.impact_score, reverse=True)
        return [self._make_feed_item(t, "undercovered", i) for i, t in enumerate(candidates)]

    def _slow_burn(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        horizon = datetime.now(timezone.utc) - timedelta(days=14)
        candidates = [
            t for t in topics
            if t.narrative_id and t.updated_at >= horizon and t.scores.market_evidence_score < 0.45 and t.scores.story_layer_score > 0.5
        ]
        candidates.sort(key=lambda t: (t.narrative_id, t.scores.impact_score), reverse=True)
        return [self._make_feed_item(t, "slow_burn", i) for i, t in enumerate(candidates)]

    def _upcoming_deadlines(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        now = datetime.now(timezone.utc)
        candidates = [
            t for t in topics
            if t.deadlines and any(0 <= (d.date - now).total_seconds() <= 10 * 86400 for d in t.deadlines)
        ]
        candidates.sort(key=lambda t: min(d.date for d in t.deadlines if d.date > now))
        return [self._make_feed_item(t, "deadlines", i) for i, t in enumerate(candidates)]

    def _make_feed_item(self, topic: ImpactTopic, section: str, position: int) -> FeedItem:
        return FeedItem(card=self._topic_to_card(topic, section), position=position, section=section)

    @staticmethod
    def _topic_to_card(topic: ImpactTopic, section: str) -> TopicCard:
        summary = ""
        if topic.what_happened:
            summary = ". ".join(topic.what_happened.split(". ")[:3]).strip()
            if summary and not summary.endswith("."):
                summary += "."
        return TopicCard(
            id=topic.id,
            slug=topic.slug,
            title=topic.title,
            category=topic.category,
            summary=summary,
            what_to_watch=topic.what_matters_next[:5],
            why_it_matters=topic.why_it_matters,
            what_changed_today=topic.what_changed_today,
            deadlines=topic.deadlines,
            citations=topic.citations,
            impact_score=topic.scores.impact_score,
            why_in_feed=topic.scores.explanation,
            section=section,
            updated_at=topic.updated_at,
        )

    def _personalize(self, items: list[FeedItem], prefs: UserPreferences) -> list[FeedItem]:
        if not prefs.geographies and not prefs.sectors:
            return items
        for item in items:
            boost = 0.0
            if any(g.lower() in item.card.title.lower() for g in prefs.geographies):
                boost += 0.1
            if any(s.lower() in item.card.category.lower() for s in prefs.sectors):
                boost += 0.1
            item.personalization_boost = boost
        items.sort(key=lambda i: i.card.impact_score + i.personalization_boost, reverse=True)
        return items

    @staticmethod
    def _empty_sections() -> list[FeedSection]:
        return [
            FeedSection(name="breaking", display_name="Breaking", items=[]),
            FeedSection(name="undercovered", display_name="Undercovered", items=[]),
            FeedSection(name="slow_burn", display_name="Slow Burn", items=[]),
            FeedSection(name="deadlines", display_name="Upcoming Deadlines", items=[]),
        ]
