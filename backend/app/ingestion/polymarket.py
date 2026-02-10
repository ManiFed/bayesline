"""Polymarket CLOB connector."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import AsyncIterator

import httpx
import structlog

from ..config import settings
from ..models.market import Market, MarketSnapshot, MarketVenue, MarketStatus
from .base import MarketConnector

logger = structlog.get_logger()


class PolymarketConnector(MarketConnector):
    venue_name = "polymarket"

    def __init__(self) -> None:
        self.base_url = settings.polymarket_api_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def fetch_active_markets(self) -> list[Market]:
        client = await self._get_client()
        markets: list[Market] = []
        next_cursor: str | None = None

        for _ in range(10):  # max pages
            params: dict = {"limit": 100, "active": True}
            if next_cursor:
                params["next_cursor"] = next_cursor

            try:
                resp = await client.get("/markets", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                logger.warning("polymarket.fetch_failed", exc_info=True)
                break

            for item in data.get("data", data) if isinstance(data, dict) else data:
                m = self._parse_market(item)
                if m:
                    markets.append(m)

            next_cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not next_cursor:
                break

        logger.info("polymarket.fetched", count=len(markets))
        return markets

    async def fetch_snapshots(self, market_ids: list[str]) -> list[MarketSnapshot]:
        client = await self._get_client()
        snapshots: list[MarketSnapshot] = []
        now = datetime.now(timezone.utc)

        for mid in market_ids:
            try:
                resp = await client.get(f"/markets/{mid}")
                resp.raise_for_status()
                item = resp.json()
                snap = MarketSnapshot(
                    market_id=f"polymarket:{mid}",
                    timestamp=now,
                    probability=self._extract_prob(item),
                    volume_usd=float(item.get("volume", 0) or 0),
                    open_interest_usd=float(item.get("openInterest", 0) or 0),
                    liquidity_usd=float(item.get("liquidity", 0) or 0),
                )
                snapshots.append(snap)
            except Exception:
                logger.warning("polymarket.snapshot_failed", market_id=mid, exc_info=True)

        return snapshots

    async def stream_updates(self) -> AsyncIterator[MarketSnapshot]:
        # Polymarket doesn't have a public websocket; poll instead
        while True:
            yield  # type: ignore[misc]
            break

    def _parse_market(self, item: dict) -> Market | None:
        try:
            venue_id = str(item.get("condition_id") or item.get("id", ""))
            if not venue_id:
                return None
            return Market(
                id=f"polymarket:{venue_id}",
                venue=MarketVenue.POLYMARKET,
                venue_id=venue_id,
                question=item.get("question", ""),
                description=item.get("description", ""),
                category=item.get("category", ""),
                tags=item.get("tags", []) or [],
                created_at=self._parse_dt(item.get("created_at")),
                close_date=self._parse_dt(item.get("end_date_iso")),
                status=MarketStatus.ACTIVE,
                current_probability=self._extract_prob(item),
                volume_usd=float(item.get("volume", 0) or 0),
                open_interest_usd=float(item.get("openInterest", 0) or 0),
                num_traders=int(item.get("uniqueTraders", 0) or 0),
                liquidity_usd=float(item.get("liquidity", 0) or 0),
                resolution_source=item.get("resolutionSource", ""),
            )
        except Exception:
            logger.warning("polymarket.parse_failed", exc_info=True)
            return None

    @staticmethod
    def _extract_prob(item: dict) -> float | None:
        tokens = item.get("tokens", [])
        if tokens and isinstance(tokens, list):
            for t in tokens:
                if t.get("outcome", "").lower() == "yes":
                    return float(t.get("price", 0.5))
        price = item.get("outcomePrices") or item.get("lastTradePrice")
        if price is not None:
            if isinstance(price, list) and len(price) > 0:
                return float(price[0])
            return float(price)
        return None

    @staticmethod
    def _parse_dt(val) -> datetime:
        if val is None:
            return datetime.now(timezone.utc)
        if isinstance(val, datetime):
            return val
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
