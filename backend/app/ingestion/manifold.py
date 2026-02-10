"""Manifold Markets connector."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

import httpx
import structlog

from ..config import settings
from ..models.market import Market, MarketSnapshot, MarketVenue, MarketStatus
from .base import MarketConnector

logger = structlog.get_logger()


class ManifoldConnector(MarketConnector):
    venue_name = "manifold"

    def __init__(self) -> None:
        self.base_url = settings.manifold_api_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
        return self._client

    async def fetch_active_markets(self) -> list[Market]:
        client = await self._get_client()
        markets: list[Market] = []

        try:
            # Fetch trending markets sorted by activity
            resp = await client.get("/search-markets", params={
                "sort": "liquidity",
                "filter": "open",
                "limit": 500,
            })
            resp.raise_for_status()
            data = resp.json()

            for item in data:
                m = self._parse_market(item)
                if m:
                    markets.append(m)
        except Exception:
            logger.warning("manifold.fetch_failed", exc_info=True)

        logger.info("manifold.fetched", count=len(markets))
        return markets

    async def fetch_snapshots(self, market_ids: list[str]) -> list[MarketSnapshot]:
        client = await self._get_client()
        snapshots: list[MarketSnapshot] = []
        now = datetime.now(timezone.utc)

        for mid in market_ids:
            raw_id = mid.replace("manifold:", "")
            try:
                resp = await client.get(f"/market/{raw_id}")
                resp.raise_for_status()
                item = resp.json()
                snapshots.append(MarketSnapshot(
                    market_id=f"manifold:{raw_id}",
                    timestamp=now,
                    probability=item.get("probability"),
                    volume_usd=float(item.get("volume", 0) or 0),
                    liquidity_usd=float(item.get("totalLiquidity", 0) or 0),
                    num_traders=int(item.get("uniqueBettorCount", 0) or 0),
                ))
            except Exception:
                logger.warning("manifold.snapshot_failed", market_id=mid, exc_info=True)

        return snapshots

    async def stream_updates(self) -> AsyncIterator[MarketSnapshot]:
        while True:
            yield  # type: ignore[misc]
            break

    def _parse_market(self, item: dict) -> Market | None:
        try:
            venue_id = item.get("id", "")
            if not venue_id:
                return None
            mechanism = item.get("mechanism", "")
            # Only binary markets for now
            if item.get("outcomeType") not in ("BINARY", None):
                return None

            created_ts = item.get("createdTime", 0)
            close_ts = item.get("closeTime")

            return Market(
                id=f"manifold:{venue_id}",
                venue=MarketVenue.MANIFOLD,
                venue_id=venue_id,
                question=item.get("question", ""),
                description=item.get("textDescription", ""),
                category=item.get("groupSlugs", [""])[0] if item.get("groupSlugs") else "",
                tags=item.get("groupSlugs", []) or [],
                created_at=datetime.fromtimestamp(created_ts / 1000, tz=timezone.utc) if created_ts else datetime.now(timezone.utc),
                close_date=datetime.fromtimestamp(close_ts / 1000, tz=timezone.utc) if close_ts else None,
                status=MarketStatus.ACTIVE if not item.get("isResolved") else MarketStatus.RESOLVED,
                current_probability=item.get("probability"),
                volume_usd=float(item.get("volume", 0) or 0),
                num_traders=int(item.get("uniqueBettorCount", 0) or 0),
                liquidity_usd=float(item.get("totalLiquidity", 0) or 0),
                has_clear_resolution=True,
            )
        except Exception:
            logger.warning("manifold.parse_failed", exc_info=True)
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
