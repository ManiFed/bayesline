"""Topic discovery and mapping — the hard part.

Detects emerging topics from market data, links them to news,
and maintains a canonical topic graph.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone

import structlog

from ..models.market import Market
from ..models.topic import ImpactTopic, TopicMarketMapping, Citation
from ..models.news import NewsArticle
from ..services.store import DataStore
from .entity_extractor import EntityExtractor
from .deduplication import MarketDeduplicator

logger = structlog.get_logger()


# Category inference from question text
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "politics": ["election", "president", "congress", "senate", "vote", "impeach", "governor", "mayor"],
    "economy": ["gdp", "recession", "inflation", "interest rate", "fed", "unemployment", "jobs"],
    "geopolitics": ["war", "invasion", "ceasefire", "nato", "sanctions", "nuclear", "missile"],
    "regulation": ["sec", "fda", "epa", "ftc", "regulation", "ban", "approve", "ruling"],
    "technology": ["ai", "tech", "openai", "google", "apple", "microsoft", "spacex", "launch"],
    "climate": ["climate", "hurricane", "wildfire", "earthquake", "emissions", "temperature"],
    "finance": ["stock", "bitcoin", "crypto", "market cap", "ipo", "merger", "bankruptcy"],
    "health": ["pandemic", "vaccine", "fda approval", "outbreak", "who", "drug"],
    "legal": ["supreme court", "ruling", "lawsuit", "trial", "indictment", "verdict"],
    "government": ["shutdown", "debt ceiling", "budget", "spending", "default"],
}


class TopicDiscovery:
    """Discovers, clusters, and maintains Impact Topics."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self.entity_extractor = EntityExtractor(store)
        self.deduplicator = MarketDeduplicator(store)

    def discover_topics(self) -> list[ImpactTopic]:
        """Main entry: discover topics from all available data."""
        markets = self.store.get_all_markets()
        if not markets:
            return []

        # Step A: Cluster markets by shared entities and outcome language
        clusters = self._cluster_markets(markets)

        # Step B: Build or update topics for each cluster
        topics: list[ImpactTopic] = []
        for cluster_key, market_group in clusters.items():
            topic = self._build_topic(cluster_key, market_group)
            if topic:
                topics.append(topic)

        logger.info("topic_discovery.discovered", count=len(topics))
        return topics

    def _cluster_markets(self, markets: list[Market]) -> dict[str, list[Market]]:
        """Group markets into topic clusters."""
        # First, use deduplicator for near-identical questions
        dedup_clusters = self.deduplicator.find_clusters(markets)

        # Build entity-based groupings
        entity_groups: dict[str, list[Market]] = defaultdict(list)
        market_by_id = {m.id: m for m in markets}

        for m in markets:
            # Extract entities from the question
            entities = self.entity_extractor.extract_from_text(m.question)
            m.entity_ids = [e.id for e in entities]
            self.store.upsert_market(m)

            # Group by primary entity combination
            entity_key = self._entity_cluster_key(entities)
            if entity_key:
                entity_groups[entity_key].append(m)

        # Merge: prefer entity-based clusters, then dedup clusters, then singles
        final_clusters: dict[str, list[Market]] = {}
        assigned: set[str] = set()

        # Entity clusters first
        for key, group in entity_groups.items():
            if len(group) >= 1:
                final_clusters[key] = group
                for m in group:
                    assigned.add(m.id)

        # Remaining unassigned markets get their own topic
        for m in markets:
            if m.id not in assigned:
                single_key = f"single:{m.id}"
                final_clusters[single_key] = [m]

        return final_clusters

    def _build_topic(
        self, cluster_key: str, markets: list[Market]
    ) -> ImpactTopic | None:
        if not markets:
            return None

        # Create or find existing topic
        topic_id = f"topic:{hashlib.sha256(cluster_key.encode()).hexdigest()[:12]}"
        existing = self.store.get_topic(topic_id)

        # Determine category
        all_text = " ".join(m.question for m in markets)
        category = self._infer_category(all_text)

        # Generate a neutral title from the primary market question
        primary = max(markets, key=lambda m: m.volume_usd)
        title = self._clean_title(primary.question)

        # Extract entities
        entities = self.entity_extractor.extract_from_text(all_text)
        entity_ids = list(set(e.id for e in entities))

        # Find related news articles
        article_ids = self._find_related_articles(title, entities)

        # Build citations from found articles
        citations = self._build_citations(article_ids)

        now = datetime.now(timezone.utc)
        topic = existing or ImpactTopic(
            id=topic_id,
            slug=self._slugify(title),
            title=title,
            created_at=now,
            first_detected_at=now,
        )

        topic.title = title
        topic.category = category
        topic.market_ids = [m.id for m in markets]
        topic.entity_ids = entity_ids
        topic.article_ids = article_ids
        topic.citations = citations
        topic.updated_at = now

        # Set up market mappings with dedup weights
        dedup_clusters = self.deduplicator.find_clusters(markets)
        mappings: list[TopicMarketMapping] = []
        for cluster_mids in dedup_clusters.values():
            weights = self.deduplicator.compute_relevance_weights(cluster_mids)
            for mid, w in weights.items():
                mappings.append(TopicMarketMapping(
                    topic_id=topic.id, market_id=mid, relevance_weight=w,
                ))

        # Markets not in any dedup cluster get weight 1.0
        mapped_ids = {m.market_id for m in mappings}
        for m in markets:
            if m.id not in mapped_ids:
                mappings.append(TopicMarketMapping(
                    topic_id=topic.id, market_id=m.id, relevance_weight=1.0,
                    is_primary=(m.id == primary.id),
                ))

        self.store.set_topic_market_mappings(topic.id, mappings)
        self.store.upsert_topic(topic)
        return topic

    def _find_related_articles(
        self, title: str, entities: list
    ) -> list[str]:
        """Search news corpus by entities and distinctive phrases."""
        article_ids: list[str] = []
        seen: set[str] = set()

        search_terms = [title]
        for e in entities[:5]:
            search_terms.append(e.name)

        for term in search_terms:
            for article in self.store.search_articles(term):
                if article.id not in seen:
                    seen.add(article.id)
                    article_ids.append(article.id)

        return article_ids[:20]

    def _build_citations(self, article_ids: list[str]) -> list[Citation]:
        """Build citations from article IDs, primary sources first."""
        citations: list[Citation] = []
        for aid in article_ids:
            article = self.store.get_article(aid)
            if article:
                citations.append(Citation(
                    source_id=article.id,
                    source_type=article.source_type.value,
                    title=article.title,
                    url=article.url,
                    excerpt=article.summary[:200] if article.summary else "",
                    is_primary=article.source_type.value != "news_article",
                ))

        # Sort: primary sources first
        citations.sort(key=lambda c: (not c.is_primary, c.title))
        return citations

    @staticmethod
    def _infer_category(text: str) -> str:
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            scores[cat] = sum(1 for kw in keywords if kw in text_lower)
        if not scores:
            return "general"
        best = max(scores, key=scores.get)  # type: ignore
        return best if scores[best] > 0 else "general"

    @staticmethod
    def _clean_title(question: str) -> str:
        """Turn a market question into a neutral topic title."""
        title = question.strip().rstrip("?").strip()
        title = re.sub(r"^(Will|Is|Are|Does|Do|Has|Have|Can|Should)\s+", "", title, flags=re.IGNORECASE)
        if len(title) > 80:
            title = title[:77] + "..."
        return title.strip()

    @staticmethod
    def _slugify(text: str) -> str:
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug).strip("-")
        return slug[:60]

    @staticmethod
    def _entity_cluster_key(entities: list) -> str:
        if not entities:
            return ""
        names = sorted(set(e.name.lower() for e in entities))[:3]
        return "+".join(names)
