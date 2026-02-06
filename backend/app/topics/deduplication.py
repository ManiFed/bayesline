"""Deduplicate near-identical prediction-market questions.

Markets often create many variants of the same question (different dates,
slight wording changes). This module clusters them into single topics.
"""

from __future__ import annotations

import re
from collections import defaultdict

import structlog

from ..models.market import Market
from ..services.store import DataStore

logger = structlog.get_logger()


def _normalize_question(text: str) -> str:
    """Normalize question text for comparison."""
    text = text.lower().strip()
    text = re.sub(r"\b(by|before|after|in|on|during)\s+\w+\s+\d{1,2},?\s*\d{2,4}", "", text)
    text = re.sub(r"\b\d{4}\b", "YEAR", text)
    text = re.sub(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", "MONTH", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_outcome_type(text: str) -> str:
    """Detect outcome type: pass, delay, exceed, resign, etc."""
    text_lower = text.lower()
    for kw in ["pass", "approve", "confirm", "ratif"]:
        if kw in text_lower:
            return "pass"
    for kw in ["delay", "postpone", "extend"]:
        if kw in text_lower:
            return "delay"
    for kw in ["exceed", "above", "over", "more than"]:
        if kw in text_lower:
            return "exceed"
    for kw in ["resign", "step down", "leave office"]:
        if kw in text_lower:
            return "resign"
    for kw in ["win", "elect", "victory"]:
        if kw in text_lower:
            return "win"
    return "other"


class MarketDeduplicator:
    """Clusters near-duplicate markets into canonical groups."""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def find_clusters(self, markets: list[Market] | None = None) -> dict[str, list[str]]:
        """Return {cluster_key: [market_ids]} for near-duplicate groups."""
        if markets is None:
            markets = self.store.get_all_markets()

        # Build signature for each market
        sigs: dict[str, list[str]] = defaultdict(list)
        for m in markets:
            sig = self._signature(m)
            sigs[sig].append(m.id)

        # Only return clusters with >1 market
        clusters = {k: v for k, v in sigs.items() if len(v) > 1}
        logger.info("deduplication.clusters", total_clusters=len(clusters))
        return clusters

    def compute_relevance_weights(
        self, cluster_market_ids: list[str]
    ) -> dict[str, float]:
        """Within a cluster, assign weights: primary market gets 1.0, rest get 0.3."""
        if not cluster_market_ids:
            return {}

        # Primary = highest liquidity
        best_id = cluster_market_ids[0]
        best_liq = 0.0
        for mid in cluster_market_ids:
            m = self.store.get_market(mid)
            if m and m.liquidity_usd > best_liq:
                best_liq = m.liquidity_usd
                best_id = mid

        weights: dict[str, float] = {}
        for mid in cluster_market_ids:
            weights[mid] = 1.0 if mid == best_id else 0.3
        return weights

    @staticmethod
    def _signature(market: Market) -> str:
        """Create a dedup signature from entities, outcome type, and normalized text."""
        norm = _normalize_question(market.question)
        outcome = _extract_outcome_type(market.question)
        # Use first few significant words + outcome type
        words = [w for w in norm.split() if len(w) > 3][:6]
        return f"{outcome}:{'_'.join(words)}"
