"""Main orchestrator that ties together ingestion, scoring, discovery, and summarization."""

from __future__ import annotations

import asyncio

import structlog

from .store import DataStore
from .feed import FeedService
from ..ingestion.market_ingestor import MarketIngestor
from ..ingestion.news_ingestor import NewsIngestor
from ..topics.discovery import TopicDiscovery
from ..scoring.impact_score import ImpactScorer
from ..summarization.pipeline import SummarizationPipeline

logger = structlog.get_logger()


class Orchestrator:
    """Runs the full pipeline: ingest → discover → score → summarize."""

    def __init__(self) -> None:
        self.store = DataStore()
        self.market_ingestor = MarketIngestor(self.store)
        self.news_ingestor = NewsIngestor(self.store)
        self.topic_discovery = TopicDiscovery(self.store)
        self.impact_scorer = ImpactScorer(self.store)
        self.summarizer = SummarizationPipeline(self.store)
        self.feed_service = FeedService(self.store)

    async def run_full_pipeline(self) -> None:
        """Execute the complete pipeline once."""
        logger.info("orchestrator.pipeline_start")

        # Phase 1: Ingest markets and news concurrently
        logger.info("orchestrator.ingesting")
        markets, articles = await asyncio.gather(
            self.market_ingestor.ingest_all(),
            self.news_ingestor.ingest_headlines(),
            return_exceptions=True,
        )
        if isinstance(markets, Exception):
            logger.error("orchestrator.market_ingest_failed", error=str(markets))
        if isinstance(articles, Exception):
            logger.error("orchestrator.news_ingest_failed", error=str(articles))

        # Phase 2: Take market snapshots
        logger.info("orchestrator.snapshotting")
        await self.market_ingestor.snapshot_all()

        # Phase 3: Discover topics
        logger.info("orchestrator.discovering_topics")
        topics = self.topic_discovery.discover_topics()
        logger.info("orchestrator.topics_discovered", count=len(topics))

        # Phase 4: Score all topics
        logger.info("orchestrator.scoring")
        self.impact_scorer.score_all_topics()

        # Phase 5: Summarize topics (LLM-dependent, may be slow)
        logger.info("orchestrator.summarizing")
        await self.summarizer.summarize_all()

        stats = self.store.stats()
        logger.info("orchestrator.pipeline_complete", **stats)

    async def run_quick_update(self) -> None:
        """Lightweight update: snapshot + rescore without full ingestion."""
        await self.market_ingestor.snapshot_all()
        self.impact_scorer.score_all_topics()

    async def close(self) -> None:
        await self.market_ingestor.close()
        await self.news_ingestor.close()
        await self.summarizer.close()
