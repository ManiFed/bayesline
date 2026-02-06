"""Feed assembly: takes scored topics and arranges them into sections.

Feed sections:
1. Breaking Importance: highest ImpactScore with recent information change.
2. Undercovered: highest CoverageGap.
3. Deadlines: upcoming resolution dates and real-world deadlines.
4. Slow-burn: high consequence but low volatility.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from ..config import settings
from ..models.topic import ImpactTopic, TopicCard, Citation, Deadline
from ..models.feed import (
    FeedItem, FeedSection, FeedResponse, UserPreferences,
)
from ..services.store import DataStore

logger = structlog.get_logger()


class FeedService:
    """Assembles the user-facing feed from scored topics."""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def build_feed(
        self,
        preferences: Optional[UserPreferences] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> FeedResponse:
        prefs = preferences or UserPreferences()
        topics = self.store.get_all_topics()

        if not topics:
            return FeedResponse(
                sections=self._empty_sections(),
                total_topics=0,
                page=page,
                page_size=page_size,
            )

        # Build feed sections
        breaking = self._breaking_importance(topics)
        undercovered = self._undercovered(topics)
        deadlines = self._deadlines(topics)
        slow_burn = self._slow_burn(topics)

        # Apply personalization (ordering adjustments only)
        breaking = self._personalize(breaking, prefs)
        undercovered = self._personalize(undercovered, prefs)
        deadlines = self._personalize(deadlines, prefs)
        slow_burn = self._personalize(slow_burn, prefs)

        # Ensure high-consequence topics always appear
        self._enforce_consequence_floor(
            [breaking, undercovered, deadlines, slow_burn], topics, prefs
        )

        sections = [
            FeedSection(
                name="breaking",
                display_name="Breaking Importance",
                description="Highest-impact topics with recent developments",
                items=breaking[:page_size],
            ),
            FeedSection(
                name="undercovered",
                display_name="Undercovered",
                description="Significant topics not yet in mainstream headlines",
                items=undercovered[:page_size // 2],
            ),
            FeedSection(
                name="deadlines",
                display_name="Upcoming Deadlines",
                description="Important dates and decision points approaching",
                items=deadlines[:page_size // 2],
            ),
            FeedSection(
                name="slow_burn",
                display_name="Slow Burn",
                description="High consequence, evolving gradually",
                items=slow_burn[:page_size // 2],
            ),
        ]

        return FeedResponse(
            sections=sections,
            total_topics=len(topics),
            page=page,
            page_size=page_size,
        )

    def _breaking_importance(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        """Highest ImpactScore with recent information change."""
        now = datetime.now(timezone.utc)
        recent = [
            t for t in topics
            if (now - t.updated_at).total_seconds() < 86400  # last 24h
        ]
        if not recent:
            recent = topics

        sorted_topics = sorted(
            recent, key=lambda t: t.scores.impact_score, reverse=True
        )
        return [
            self._make_feed_item(t, "breaking", i)
            for i, t in enumerate(sorted_topics)
        ]

    def _undercovered(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        """Highest CoverageGap — traders care more than editors."""
        sorted_topics = sorted(
            topics, key=lambda t: t.scores.coverage_gap, reverse=True
        )
        return [
            self._make_feed_item(t, "undercovered", i)
            for i, t in enumerate(sorted_topics)
            if t.scores.coverage_gap > 0.1
        ]

    def _deadlines(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        """Topics with upcoming deadlines, sorted by nearest date."""
        now = datetime.now(timezone.utc)
        with_deadlines = [
            t for t in topics
            if t.deadlines and any(d.date > now for d in t.deadlines)
        ]

        # Also include high time sensitivity topics
        high_ts = [
            t for t in topics
            if t.scores.time_sensitivity > 0.6 and t not in with_deadlines
        ]
        with_deadlines.extend(high_ts)

        def nearest_deadline(t: ImpactTopic) -> datetime:
            future = [d.date for d in t.deadlines if d.date > now]
            return min(future) if future else now + timedelta(days=365)

        sorted_topics = sorted(with_deadlines, key=nearest_deadline)
        return [
            self._make_feed_item(t, "deadlines", i)
            for i, t in enumerate(sorted_topics)
        ]

    def _slow_burn(self, topics: list[ImpactTopic]) -> list[FeedItem]:
        """High consequence, low volatility."""
        candidates = [
            t for t in topics
            if t.scores.expected_consequence > 0.5
            and t.scores.market_signal < 0.4  # low recent volatility
        ]
        sorted_topics = sorted(
            candidates,
            key=lambda t: t.scores.expected_consequence,
            reverse=True,
        )
        return [
            self._make_feed_item(t, "slow_burn", i)
            for i, t in enumerate(sorted_topics)
        ]

    def _make_feed_item(
        self, topic: ImpactTopic, section: str, position: int
    ) -> FeedItem:
        card = self._topic_to_card(topic, section)
        return FeedItem(card=card, position=position, section=section)

    @staticmethod
    def _topic_to_card(topic: ImpactTopic, section: str) -> TopicCard:
        """Convert internal ImpactTopic to user-facing TopicCard (no market data)."""
        # Build three-sentence summary
        summary_parts = []
        if topic.what_happened:
            sentences = topic.what_happened.split(". ")
            summary_parts.extend(sentences[:3])
        summary = ". ".join(summary_parts).strip()
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

    def _personalize(
        self, items: list[FeedItem], prefs: UserPreferences
    ) -> list[FeedItem]:
        """Adjust ordering based on user preferences (not filtering truth)."""
        if not prefs.geographies and not prefs.sectors:
            return items

        for item in items:
            boost = 0.0
            cat = item.card.category.lower()

            # Geography match
            if prefs.geographies:
                for geo in prefs.geographies:
                    if geo.lower() in item.card.title.lower():
                        boost += 0.1

            # Sector match
            if prefs.sectors:
                for sector in prefs.sectors:
                    if sector.lower() in cat:
                        boost += 0.1

            # Preference for undercovered
            if prefs.prefer_undercovered and item.section == "undercovered":
                boost += 0.05

            # Preference for deadlines
            if prefs.prefer_deadlines and item.section == "deadlines":
                boost += 0.05

            item.personalization_boost = boost

        # Re-sort within section by impact_score + boost
        items.sort(
            key=lambda i: i.card.impact_score + i.personalization_boost,
            reverse=True,
        )
        return items

    def _enforce_consequence_floor(
        self,
        all_sections: list[list[FeedItem]],
        topics: list[ImpactTopic],
        prefs: UserPreferences,
    ) -> None:
        """Always keep high-consequence topics regardless of personalization."""
        floor = prefs.min_consequence_floor
        shown_ids: set[str] = set()
        for section in all_sections:
            for item in section:
                shown_ids.add(item.card.id)

        for topic in topics:
            if (
                topic.scores.expected_consequence >= floor
                and topic.id not in shown_ids
            ):
                item = self._make_feed_item(topic, "breaking", 0)
                all_sections[0].append(item)

    @staticmethod
    def _empty_sections() -> list[FeedSection]:
        return [
            FeedSection(name="breaking", display_name="Breaking Importance", items=[]),
            FeedSection(name="undercovered", display_name="Undercovered", items=[]),
            FeedSection(name="deadlines", display_name="Upcoming Deadlines", items=[]),
            FeedSection(name="slow_burn", display_name="Slow Burn", items=[]),
        ]
