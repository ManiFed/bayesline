"""Extract entities from market questions and news text.

Uses rule-based NER patterns. In production, replace with spaCy or a fine-tuned model.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import structlog

from ..models.entity import Entity, EntityType
from ..services.store import DataStore

logger = structlog.get_logger()

# Keyword patterns for entity type detection
COUNTRY_NAMES = {
    "united states", "us", "usa", "china", "russia", "ukraine", "india",
    "uk", "united kingdom", "france", "germany", "japan", "brazil",
    "canada", "australia", "iran", "israel", "north korea", "south korea",
    "taiwan", "mexico", "turkey", "saudi arabia", "eu", "european union",
}

AGENCY_PATTERNS = [
    r"\b(SEC|FDA|EPA|DOJ|FBI|CIA|NSA|DOD|DHS|FEMA|FCC|FTC|CFPB|NTSB)\b",
    r"\b(Federal Reserve|Fed|Treasury|Congress|Senate|House)\b",
    r"\b(Supreme Court|WHO|NATO|UN|IMF|World Bank|WTO)\b",
    r"\b(ECB|Bank of England|Bank of Japan|PBOC)\b",
]

EVENT_PATTERNS = [
    r"(?:government\s+)?shutdown",
    r"debt\s+ceiling",
    r"election",
    r"impeach",
    r"recession",
    r"default",
    r"cease\s*fire",
    r"invasion",
    r"pandemic",
    r"hurricane|earthquake|tsunami|wildfire",
]


class EntityExtractor:
    """Extracts and upserts entities from text content."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self._agency_re = re.compile("|".join(AGENCY_PATTERNS), re.IGNORECASE)
        self._event_re = re.compile(
            "|".join(f"({p})" for p in EVENT_PATTERNS), re.IGNORECASE
        )

    def extract_from_text(self, text: str) -> list[Entity]:
        """Extract entities from arbitrary text, upsert to store, return list."""
        entities: list[Entity] = []
        text_lower = text.lower()

        # Countries
        for country in COUNTRY_NAMES:
            if country in text_lower:
                eid = self._make_id("country", country)
                entity = Entity(
                    id=eid,
                    entity_type=EntityType.COUNTRY,
                    name=country.title(),
                )
                self.store.upsert_entity(entity)
                entities.append(entity)

        # Agencies / organizations
        for match in self._agency_re.finditer(text):
            name = match.group(0).strip()
            eid = self._make_id("org", name.lower())
            entity = Entity(
                id=eid,
                entity_type=EntityType.GOVERNMENT_AGENCY,
                name=name,
            )
            self.store.upsert_entity(entity)
            entities.append(entity)

        # Events
        for match in self._event_re.finditer(text):
            name = match.group(0).strip()
            eid = self._make_id("event", name.lower())
            entity = Entity(
                id=eid,
                entity_type=EntityType.EVENT,
                name=name.title(),
            )
            self.store.upsert_entity(entity)
            entities.append(entity)

        return entities

    @staticmethod
    def _make_id(prefix: str, name: str) -> str:
        h = hashlib.sha256(name.encode()).hexdigest()[:10]
        return f"{prefix}:{h}"
