"""Orchestrator that polls all market venues and stores snapshots."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from ..models.market import Market, MarketSnapshot
from .base import MarketConnector
from .polymarket import PolymarketConnector
from .manifold import ManifoldConnector
from .kalshi import KalshiConnector
from ..services.store import DataStore

logger = structlog.get_logger()


class MarketIngestor:
    """Fetches markets from all venues, stores snapshots, returns unified view."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self.connectors: list[MarketConnector] = [
            PolymarketConnector(),
            ManifoldConnector(),
            KalshiConnector(),
        ]

    async def ingest_all(self) -> list[Market]:
        """Fetch active markets from all venues concurrently.

        Each venue gets a 15-second timeout so one slow/down API cannot
        block the entire ingestion cycle.
        """
        async def _fetch_with_timeout(c: MarketConnector) -> list[Market]:
            return await asyncio.wait_for(c.fetch_active_markets(), timeout=15)

        results = await asyncio.gather(
            *[_fetch_with_timeout(c) for c in self.connectors],
            return_exceptions=True,
        )

        all_markets: list[Market] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "market_ingestor.venue_failed",
                    venue=self.connectors[i].venue_name,
                    error=str(result),
                )
                continue
            all_markets.extend(result)

        # Store markets
        for m in all_markets:
            self.store.upsert_market(m)

        logger.info("market_ingestor.ingested", total=len(all_markets))
        return all_markets

    async def snapshot_all(self) -> list[MarketSnapshot]:
        """Take a snapshot of all known active markets."""
        snapshots: list[MarketSnapshot] = []

        for connector in self.connectors:
            venue = connector.venue_name
            market_ids = self.store.get_market_ids_by_venue(venue)
            if not market_ids:
                continue
            try:
                batch = await connector.fetch_snapshots(market_ids[:200])
                snapshots.extend(batch)
            except Exception:
                logger.error("market_ingestor.snapshot_failed", venue=venue, exc_info=True)

        for snap in snapshots:
            self.store.append_snapshot(snap)

        logger.info("market_ingestor.snapshots", count=len(snapshots))
        return snapshots

    async def close(self) -> None:
        for c in self.connectors:
            if hasattr(c, "close"):
                await c.close()
