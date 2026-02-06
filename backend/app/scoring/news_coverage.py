"""Step 3: Compute NewsCoverage(t) and CoverageGap / HypeGap."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import structlog

from ..models.topic import ImpactTopic
from ..models.news import NewsArticle
from ..services.store import DataStore

logger = structlog.get_logger()


class NewsCoverageScorer:
    """Scores how much news coverage a topic is receiving."""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def compute(self, topic: ImpactTopic) -> float:
        """Return NewsCoverage(t) in [0, 1]."""
        articles = self._find_related_articles(topic)
        if not articles:
            return 0.0

        now = datetime.now(timezone.utc)

        # Factor 1: Number of distinct outlets
        outlets = set(a.source_name for a in articles if a.source_name)
        outlet_score = min(len(outlets) / 15.0, 1.0)  # 15+ outlets = max

        # Factor 2: Prominence (front page, top section)
        prominence_scores = [a.prominence_score for a in articles]
        avg_prominence = sum(prominence_scores) / len(prominence_scores) if prominence_scores else 0.0

        # Factor 3: Volume of articles (deduplicated via cluster_id)
        clusters = set()
        unique_count = 0
        for a in articles:
            key = a.cluster_id or a.id
            if key not in clusters:
                clusters.add(key)
                unique_count += 1
        volume_score = min(unique_count / 20.0, 1.0)

        # Factor 4: Recency — exponential decay, most recent dominates
        recency_scores = []
        for a in articles:
            if a.published_at:
                hours_ago = (now - a.published_at).total_seconds() / 3600
                recency_scores.append(math.exp(-hours_ago / 24.0))
        recency = max(recency_scores) if recency_scores else 0.0

        coverage = (
            0.30 * outlet_score
            + 0.20 * avg_prominence
            + 0.25 * volume_score
            + 0.25 * recency
        )
        return max(0.0, min(1.0, coverage))

    def compute_gaps(
        self, topic: ImpactTopic, market_signal: float
    ) -> tuple[float, float]:
        """Return (CoverageGap, HypeGap) for the topic."""
        news_coverage = self.compute(topic)
        coverage_gap = max(0.0, market_signal - news_coverage)
        hype_gap = max(0.0, news_coverage - market_signal)
        return coverage_gap, hype_gap

    def _find_related_articles(self, topic: ImpactTopic) -> list[NewsArticle]:
        """Find articles related to this topic by ID list or text search."""
        articles: list[NewsArticle] = []

        # Direct ID mapping
        for aid in topic.article_ids:
            a = self.store.get_article(aid)
            if a:
                articles.append(a)

        # Text search by topic title and entity names
        if not articles:
            search_terms = [topic.title]
            for eid in topic.entity_ids[:5]:
                entity = self.store.get_entity(eid)
                if entity:
                    search_terms.append(entity.name)

            for term in search_terms:
                articles.extend(self.store.search_articles(term))

        return articles
