"""Base classes for market and news connectors."""

from __future__ import annotations

import abc
from typing import AsyncIterator

from ..models.market import Market, MarketSnapshot
from ..models.news import NewsArticle


class MarketConnector(abc.ABC):
    """Abstract base for prediction-market venue connectors."""

    venue_name: str = ""

    @abc.abstractmethod
    async def fetch_active_markets(self) -> list[Market]:
        """Return all active markets from this venue."""
        ...

    @abc.abstractmethod
    async def fetch_snapshots(self, market_ids: list[str]) -> list[MarketSnapshot]:
        """Return current snapshots for the given market IDs."""
        ...

    @abc.abstractmethod
    async def stream_updates(self) -> AsyncIterator[MarketSnapshot]:
        """Yield real-time updates if the venue supports them."""
        ...


class NewsConnector(abc.ABC):
    """Abstract base for news source connectors."""

    source_name: str = ""

    @abc.abstractmethod
    async def fetch_latest(self, query: str | None = None) -> list[NewsArticle]:
        """Fetch latest articles, optionally filtered by query."""
        ...
