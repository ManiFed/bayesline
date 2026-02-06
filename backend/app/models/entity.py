"""Entity and topic graph models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    COMPANY = "company"
    GOVERNMENT_AGENCY = "government_agency"
    COUNTRY = "country"
    LEGISLATION = "legislation"
    EVENT = "event"
    CLAIM = "claim"


class Entity(BaseModel):
    """A node in the entity/topic graph."""

    id: str
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""

    # Metadata for consequence scoring
    population_affected: Optional[int] = None
    gdp_exposure_usd: Optional[float] = None
    sector: str = ""
    jurisdiction: str = ""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RelationType(str, Enum):
    RELATED_TO = "related_to"
    CAUSES = "causes"
    PART_OF = "part_of"
    OPPOSES = "opposes"
    SUPPORTS = "supports"
    DEPENDS_ON = "depends_on"


class EntityRelation(BaseModel):
    """An edge in the entity/topic graph."""

    source_id: str
    target_id: str
    relation_type: RelationType = RelationType.RELATED_TO
    weight: float = 1.0
    context: str = ""
