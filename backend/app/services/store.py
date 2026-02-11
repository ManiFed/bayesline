"""In-memory data store with persistence hooks.

In production this would be backed by TimescaleDB + document store + graph DB.
For the MVP, we keep everything in memory with simple dict-based indexes.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import structlog

from ..models.market import Market, MarketSnapshot
from ..models.news import NewsArticle, PrimarySource
from ..models.topic import ImpactTopic, TopicMarketMapping
from ..models.entity import Entity, EntityRelation
from ..models.narrative import Narrative

logger = structlog.get_logger()


class DataStore:
    """Thread-safe in-memory data store for the MVP."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Markets
        self._markets: dict[str, Market] = {}
        self._snapshots: dict[str, list[MarketSnapshot]] = defaultdict(list)

        # News
        self._articles: dict[str, NewsArticle] = {}
        self._primary_sources: dict[str, PrimarySource] = {}

        # Topics
        self._topics: dict[str, ImpactTopic] = {}
        self._topic_market_map: dict[str, list[TopicMarketMapping]] = defaultdict(list)

        # Entities
        self._entities: dict[str, Entity] = {}
        self._relations: list[EntityRelation] = []

        # Narratives
        self._narratives: dict[str, Narrative] = {}

    # ── Markets ──────────────────────────────────────────────────────────

    def upsert_market(self, market: Market) -> None:
        with self._lock:
            self._markets[market.id] = market

    def get_market(self, market_id: str) -> Optional[Market]:
        return self._markets.get(market_id)

    def get_all_markets(self) -> list[Market]:
        return list(self._markets.values())

    def get_market_ids_by_venue(self, venue: str) -> list[str]:
        return [
            m.venue_id for m in self._markets.values()
            if m.venue.value == venue
        ]

    def append_snapshot(self, snapshot: MarketSnapshot) -> None:
        with self._lock:
            snaps = self._snapshots[snapshot.market_id]
            snaps.append(snapshot)
            # Keep last 2000 snapshots per market
            if len(snaps) > 2000:
                self._snapshots[snapshot.market_id] = snaps[-2000:]

    def get_snapshots(
        self, market_id: str, since: Optional[datetime] = None
    ) -> list[MarketSnapshot]:
        snaps = self._snapshots.get(market_id, [])
        if since:
            snaps = [s for s in snaps if s.timestamp >= since]
        return snaps

    # ── News ─────────────────────────────────────────────────────────────

    def upsert_article(self, article: NewsArticle) -> None:
        with self._lock:
            self._articles[article.id] = article

    def get_article(self, article_id: str) -> Optional[NewsArticle]:
        return self._articles.get(article_id)

    def get_all_articles(self) -> list[NewsArticle]:
        return list(self._articles.values())

    def search_articles(self, query: str) -> list[NewsArticle]:
        q = query.lower()
        return [
            a for a in self._articles.values()
            if q in a.title.lower() or q in a.text.lower()
        ]

    def upsert_primary_source(self, source: PrimarySource) -> None:
        with self._lock:
            self._primary_sources[source.id] = source

    def get_primary_sources(self) -> list[PrimarySource]:
        return list(self._primary_sources.values())

    # ── Topics ───────────────────────────────────────────────────────────

    def upsert_topic(self, topic: ImpactTopic) -> None:
        with self._lock:
            topic.updated_at = datetime.now(timezone.utc)
            self._topics[topic.id] = topic

    def get_topic(self, topic_id: str) -> Optional[ImpactTopic]:
        return self._topics.get(topic_id)

    def get_all_topics(self) -> list[ImpactTopic]:
        return list(self._topics.values())

    def set_topic_market_mappings(
        self, topic_id: str, mappings: list[TopicMarketMapping]
    ) -> None:
        with self._lock:
            self._topic_market_map[topic_id] = mappings

    def get_topic_market_mappings(self, topic_id: str) -> list[TopicMarketMapping]:
        return self._topic_market_map.get(topic_id, [])

    # ── Entities ─────────────────────────────────────────────────────────

    def upsert_entity(self, entity: Entity) -> None:
        with self._lock:
            self._entities[entity.id] = entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def get_all_entities(self) -> list[Entity]:
        return list(self._entities.values())

    def add_relation(self, relation: EntityRelation) -> None:
        with self._lock:
            self._relations.append(relation)

    def get_relations(self, entity_id: str) -> list[EntityRelation]:
        return [
            r for r in self._relations
            if r.source_id == entity_id or r.target_id == entity_id
        ]


    # ── Narratives ───────────────────────────────────────────────────────

    def upsert_narrative(self, narrative: Narrative) -> None:
        with self._lock:
            self._narratives[narrative.id] = narrative

    def get_narrative(self, narrative_id: str) -> Optional[Narrative]:
        return self._narratives.get(narrative_id)

    def get_all_narratives(self) -> list[Narrative]:
        return list(self._narratives.values())

    # ── Stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "markets": len(self._markets),
            "snapshots": sum(len(v) for v in self._snapshots.values()),
            "articles": len(self._articles),
            "primary_sources": len(self._primary_sources),
            "topics": len(self._topics),
            "entities": len(self._entities),
            "relations": len(self._relations),
            "narratives": len(self._narratives),
        }
