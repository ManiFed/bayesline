"""News and primary-source ingestion from multiple providers."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from ..config import settings
from ..models.news import NewsArticle, PrimarySource, SourceType
from ..services.store import DataStore

logger = structlog.get_logger()


class NewsIngestor:
    """Fetches headlines and articles from news APIs and GDELT."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def ingest_headlines(self, queries: list[str] | None = None) -> list[NewsArticle]:
        """Fetch latest headlines from configured news sources."""
        articles: list[NewsArticle] = []

        # NewsAPI.org
        if settings.newsapi_key:
            articles.extend(await self._fetch_newsapi(queries))

        # GDELT
        articles.extend(await self._fetch_gdelt(queries))

        # Deduplicate by content hash
        seen: set[str] = set()
        unique: list[NewsArticle] = []
        for a in articles:
            h = a.content_hash or hashlib.sha256(
                (a.title + a.source_name).encode()
            ).hexdigest()[:16]
            if h not in seen:
                seen.add(h)
                a.content_hash = h
                unique.append(a)

        for a in unique:
            self.store.upsert_article(a)

        logger.info("news_ingestor.ingested", total=len(unique))
        return unique

    async def _fetch_newsapi(self, queries: list[str] | None) -> list[NewsArticle]:
        client = await self._get_client()
        articles: list[NewsArticle] = []

        try:
            # Fetch top headlines
            resp = await client.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "pageSize": 100, "apiKey": settings.newsapi_key},
            )
            resp.raise_for_status()
            for item in resp.json().get("articles", []):
                articles.append(self._parse_newsapi_article(item))
        except Exception:
            logger.warning("newsapi.headlines_failed", exc_info=True)

        # Query-based search
        if queries:
            for q in queries[:10]:
                try:
                    resp = await client.get(
                        "https://newsapi.org/v2/everything",
                        params={"q": q, "pageSize": 20, "sortBy": "publishedAt", "apiKey": settings.newsapi_key},
                    )
                    resp.raise_for_status()
                    for item in resp.json().get("articles", []):
                        articles.append(self._parse_newsapi_article(item))
                except Exception:
                    logger.warning("newsapi.query_failed", query=q, exc_info=True)

        return articles

    async def _fetch_gdelt(self, queries: list[str] | None) -> list[NewsArticle]:
        """Fetch from GDELT DOC 2.0 API for broad global coverage."""
        client = await self._get_client()
        articles: list[NewsArticle] = []

        search_terms = queries or ["politics", "economy", "conflict", "climate"]
        for term in search_terms[:5]:
            try:
                resp = await client.get(
                    f"{settings.gdelt_api_url}/doc/doc",
                    params={
                        "query": term,
                        "mode": "artlist",
                        "maxrecords": 50,
                        "format": "json",
                        "sort": "datedesc",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("articles", []):
                    articles.append(NewsArticle(
                        id=f"gdelt:{hashlib.sha256(item.get('url', '').encode()).hexdigest()[:12]}",
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        source_name=item.get("domain", ""),
                        source_type=SourceType.NEWS_ARTICLE,
                        published_at=self._parse_gdelt_date(item.get("seendate")),
                        prominence_score=0.5,
                    ))
            except Exception:
                logger.warning("gdelt.fetch_failed", term=term, exc_info=True)

        return articles

    def _parse_newsapi_article(self, item: dict) -> NewsArticle:
        url = item.get("url", "")
        return NewsArticle(
            id=f"newsapi:{hashlib.sha256(url.encode()).hexdigest()[:12]}",
            url=url,
            title=item.get("title", ""),
            text=item.get("content", "") or item.get("description", ""),
            summary=item.get("description", ""),
            source_name=item.get("source", {}).get("name", ""),
            source_type=SourceType.NEWS_ARTICLE,
            authors=[item["author"]] if item.get("author") else [],
            published_at=self._parse_iso(item.get("publishedAt")),
        )

    @staticmethod
    def _parse_iso(val) -> Optional[datetime]:
        if not val:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _parse_gdelt_date(val) -> Optional[datetime]:
        if not val:
            return None
        try:
            return datetime.strptime(str(val)[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
