"""Step 4: Expected Consequence scoring.

Rules + model hybrid that estimates the scale of real-world impact
even when prediction markets are just emerging.
"""

from __future__ import annotations

import structlog

from ..models.topic import ImpactTopic
from ..models.entity import Entity, EntityType
from ..services.store import DataStore

logger = structlog.get_logger()

# Category-level base consequence scores
CATEGORY_BASE_SCORES: dict[str, float] = {
    "war": 0.9,
    "conflict": 0.85,
    "nuclear": 0.95,
    "pandemic": 0.9,
    "financial_crisis": 0.85,
    "government_shutdown": 0.7,
    "election": 0.7,
    "legislation": 0.6,
    "regulation": 0.55,
    "trade": 0.6,
    "climate": 0.65,
    "technology": 0.5,
    "sports": 0.15,
    "entertainment": 0.1,
    "crypto": 0.35,
}

# Tail-risk categories that get a floor
TAIL_RISK_CATEGORIES = {
    "war", "nuclear", "pandemic", "financial_crisis", "conflict",
    "infrastructure", "cybersecurity",
}

# Policy irreversibility keywords
IRREVERSIBILITY_KEYWORDS = [
    "constitutional", "treaty", "amendment", "supreme court",
    "permanent", "abolish", "ratif",
]


class ConsequenceScorer:
    """Estimates Expected Consequence(t) in [0, 1]."""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def compute(self, topic: ImpactTopic) -> float:
        scores: list[float] = []

        # 1. Category base score
        cat = topic.category.lower().replace(" ", "_")
        base = CATEGORY_BASE_SCORES.get(cat, 0.4)
        scores.append(base)

        # 2. Affected population scale
        pop_score = self._population_scale(topic)
        if pop_score > 0:
            scores.append(pop_score)

        # 3. Financial magnitude
        fin_score = self._financial_magnitude(topic)
        if fin_score > 0:
            scores.append(fin_score)

        # 4. Policy irreversibility
        irrev = self._irreversibility(topic)
        if irrev > 0:
            scores.append(irrev)

        # 5. Tail-risk floor
        if cat in TAIL_RISK_CATEGORIES:
            scores.append(0.7)

        # Combine: weighted average leaning toward the max
        if not scores:
            return 0.3
        avg = sum(scores) / len(scores)
        mx = max(scores)
        combined = 0.4 * avg + 0.6 * mx
        return max(0.0, min(1.0, combined))

    def _population_scale(self, topic: ImpactTopic) -> float:
        """Estimate affected population from linked entities."""
        max_pop = 0
        for eid in topic.entity_ids:
            entity = self.store.get_entity(eid)
            if entity and entity.population_affected:
                max_pop = max(max_pop, entity.population_affected)

        if max_pop == 0:
            return 0.0
        if max_pop > 100_000_000:
            return 0.9
        if max_pop > 10_000_000:
            return 0.7
        if max_pop > 1_000_000:
            return 0.5
        if max_pop > 100_000:
            return 0.3
        return 0.15

    def _financial_magnitude(self, topic: ImpactTopic) -> float:
        """Estimate financial exposure from linked entities."""
        max_gdp = 0.0
        for eid in topic.entity_ids:
            entity = self.store.get_entity(eid)
            if entity and entity.gdp_exposure_usd:
                max_gdp = max(max_gdp, entity.gdp_exposure_usd)

        if max_gdp == 0:
            return 0.0
        if max_gdp > 1e12:     # > $1T
            return 0.9
        if max_gdp > 100e9:    # > $100B
            return 0.7
        if max_gdp > 10e9:     # > $10B
            return 0.5
        if max_gdp > 1e9:      # > $1B
            return 0.3
        return 0.15

    def _irreversibility(self, topic: ImpactTopic) -> float:
        """Check if the topic involves irreversible policy decisions."""
        text = (topic.title + " " + topic.what_happened).lower()
        matches = sum(1 for kw in IRREVERSIBILITY_KEYWORDS if kw in text)
        if matches >= 2:
            return 0.8
        if matches == 1:
            return 0.5
        return 0.0
