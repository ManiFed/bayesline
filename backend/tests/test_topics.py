"""Tests for topic discovery, deduplication, and entity extraction."""

from datetime import datetime, timezone

from app.models.market import Market, MarketVenue, MarketStatus
from app.services.store import DataStore
from app.topics.entity_extractor import EntityExtractor
from app.topics.deduplication import MarketDeduplicator
from app.topics.discovery import TopicDiscovery


def _make_market(mid: str, question: str, volume: float = 1000) -> Market:
    return Market(
        id=mid,
        venue=MarketVenue.POLYMARKET,
        venue_id=mid,
        question=question,
        created_at=datetime.now(timezone.utc),
        status=MarketStatus.ACTIVE,
        volume_usd=volume,
    )


class TestEntityExtractor:
    def test_extracts_countries(self):
        store = DataStore()
        extractor = EntityExtractor(store)
        entities = extractor.extract_from_text(
            "Will the United States impose new sanctions on China?"
        )
        names = [e.name.lower() for e in entities]
        assert any("united states" in n for n in names)
        assert any("china" in n for n in names)

    def test_extracts_agencies(self):
        store = DataStore()
        extractor = EntityExtractor(store)
        entities = extractor.extract_from_text(
            "Will the SEC approve the Bitcoin ETF before the Federal Reserve meets?"
        )
        names = [e.name for e in entities]
        assert any("SEC" in n for n in names)
        assert any("Federal Reserve" in n for n in names)

    def test_extracts_events(self):
        store = DataStore()
        extractor = EntityExtractor(store)
        entities = extractor.extract_from_text(
            "Government shutdown looms as debt ceiling deadline approaches"
        )
        names = [e.name.lower() for e in entities]
        assert any("shutdown" in n for n in names)
        assert any("debt ceiling" in n for n in names)


class TestMarketDeduplicator:
    def test_identifies_duplicates(self):
        store = DataStore()
        m1 = _make_market("m1", "Will the government shutdown happen in 2025?")
        m2 = _make_market("m2", "Will the government shutdown happen in 2026?")
        m3 = _make_market("m3", "Will Bitcoin exceed $100k?")
        store.upsert_market(m1)
        store.upsert_market(m2)
        store.upsert_market(m3)

        dedup = MarketDeduplicator(store)
        clusters = dedup.find_clusters([m1, m2, m3])

        # m1 and m2 should be in same cluster (similar after date normalization)
        # m3 should be separate
        found_dup_cluster = False
        for cluster_ids in clusters.values():
            if "m1" in cluster_ids and "m2" in cluster_ids:
                found_dup_cluster = True
        assert found_dup_cluster

    def test_relevance_weights(self):
        store = DataStore()
        m1 = _make_market("m1", "test", volume=100)
        m1.liquidity_usd = 100
        m2 = _make_market("m2", "test", volume=10000)
        m2.liquidity_usd = 50000
        store.upsert_market(m1)
        store.upsert_market(m2)

        dedup = MarketDeduplicator(store)
        weights = dedup.compute_relevance_weights(["m1", "m2"])
        assert weights["m2"] == 1.0  # Higher liquidity = primary
        assert weights["m1"] == 0.3  # Duplicate


class TestTopicDiscovery:
    def test_discovers_topics_from_markets(self):
        store = DataStore()
        m1 = _make_market("m1", "Will the US government shutdown in 2025?", 5000)
        m2 = _make_market("m2", "Will Congress pass the budget bill?", 3000)
        m3 = _make_market("m3", "Will Bitcoin reach $200k?", 8000)
        store.upsert_market(m1)
        store.upsert_market(m2)
        store.upsert_market(m3)

        discovery = TopicDiscovery(store)
        topics = discovery.discover_topics()

        assert len(topics) >= 1
        # Each topic should have a title and market_ids
        for t in topics:
            assert t.title
            assert len(t.market_ids) >= 1

    def test_category_inference(self):
        store = DataStore()
        m = _make_market("m1", "Will the Federal Reserve raise interest rates again?")
        store.upsert_market(m)

        discovery = TopicDiscovery(store)
        topics = discovery.discover_topics()

        assert len(topics) >= 1
        # Should be classified as economy
        categories = [t.category for t in topics]
        assert any(c in ("economy", "regulation") for c in categories)
