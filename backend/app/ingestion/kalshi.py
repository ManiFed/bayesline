"""Kalshi connector (US-regulated exchange)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

import httpx
import structlog

from ..config import settings
from ..models.market import Market, MarketSnapshot, MarketVenue, MarketStatus
from .base import MarketConnector

logger = structlog.get_logger()


class KalshiConnector(MarketConnector):
    venue_name = "kalshi"

    def __init__(self) -> None:
        self.base_url = settings.kalshi_api_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Accept": "application/json"}
            if settings.kalshi_api_key:
                headers["Authorization"] = f"Bearer {settings.kalshi_api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers=headers,
            )
        return self._client

    async def fetch_active_markets(self) -> list[Market]:
        client = await self._get_client()
        markets: list[Market] = []
        cursor: str | None = None

        for _ in range(10):
            params: dict = {"limit": 200, "status": "open"}
            if cursor:
                params["cursor"] = cursor

            try:
                resp = await client.get("/markets", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                logger.warning("kalshi.fetch_failed", exc_info=True)
                break

            for item in data.get("markets", []):
                m = self._parse_market(item)
                if m:
                    markets.append(m)

            cursor = data.get("cursor")
            if not cursor:
                break

        logger.info("kalshi.fetched", count=len(markets))
        return markets

    async def fetch_snapshots(self, market_ids: list[str]) -> list[MarketSnapshot]:
        client = await self._get_client()
        snapshots: list[MarketSnapshot] = []
        now = datetime.now(timezone.utc)

        for mid in market_ids:
            ticker = mid.replace("kalshi:", "")
            try:
                resp = await client.get(f"/markets/{ticker}")
                resp.raise_for_status()
                item = resp.json().get("market", {})
                yes_price = item.get("yes_bid") or item.get("last_price") or 0
                no_price = item.get("no_bid") or 0
                spread = None
                if item.get("yes_bid") and item.get("yes_ask"):
                    spread = float(item["yes_ask"]) - float(item["yes_bid"])

                snapshots.append(MarketSnapshot(
                    market_id=f"kalshi:{ticker}",
                    timestamp=now,
                    probability=float(yes_price) / 100 if yes_price else None,
                    volume_usd=float(item.get("volume", 0) or 0),
                    open_interest_usd=float(item.get("open_interest", 0) or 0),
                    bid=float(yes_price) / 100 if yes_price else None,
                    ask=float(item.get("yes_ask", 0) or 0) / 100,
                    spread=spread / 100 if spread else None,
                ))
            except Exception:
                logger.warning("kalshi.snapshot_failed", market_id=mid, exc_info=True)

        return snapshots

    async def stream_updates(self) -> AsyncIterator[MarketSnapshot]:
        while True:
            yield  # type: ignore[misc]
            break

    def _parse_market(self, item: dict) -> Market | None:
        try:
            ticker = item.get("ticker", "")
            if not ticker:
                return None

            yes_price = item.get("yes_bid") or item.get("last_price")

            return Market(
                id=f"kalshi:{ticker}",
                venue=MarketVenue.KALSHI,
                venue_id=ticker,
                question=item.get("title", ""),
                description=item.get("rules_primary", ""),
                category=item.get("category", ""),
                tags=[item.get("category", "")] if item.get("category") else [],
                created_at=self._parse_dt(item.get("open_time")),
                close_date=self._parse_dt(item.get("close_time")),
                status=MarketStatus.ACTIVE,
                current_probability=float(yes_price) / 100 if yes_price else None,
                volume_usd=float(item.get("volume", 0) or 0),
                open_interest_usd=float(item.get("open_interest", 0) or 0),
                resolution_source=item.get("settlement_source_url", ""),
                has_clear_resolution=True,
            )
        except Exception:
            logger.warning("kalshi.parse_failed", exc_info=True)
            return None

    @staticmethod
    def _parse_dt(val) -> datetime:
        if val is None:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
