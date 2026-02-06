"""Feed and personalization models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .topic import TopicCard


class UserPreferences(BaseModel):
    """User personalization controls — adjusts ordering, not truth."""

    user_id: str = "anonymous"
    geographies: list[str] = Field(default_factory=list)  # e.g. ["US", "EU"]
    sectors: list[str] = Field(default_factory=list)       # e.g. ["tech", "energy"]
    severity_preference: str = "balanced"  # "high_only", "balanced", "all"
    prefer_undercovered: bool = False
    prefer_deadlines: bool = False

    # Fixed floor: always keep high-consequence topics regardless of taste
    min_consequence_floor: float = 0.3


class FeedItem(BaseModel):
    """A single item in the feed."""

    card: TopicCard
    position: int = 0
    section: str = ""
    personalization_boost: float = 0.0


class FeedSection(BaseModel):
    """A named section of the feed."""

    name: str
    display_name: str
    description: str = ""
    items: list[FeedItem] = Field(default_factory=list)


class FeedResponse(BaseModel):
    """Complete feed response to the client."""

    sections: list[FeedSection] = Field(default_factory=list)
    total_topics: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    page: int = 1
    page_size: int = 20

    # Alert topics (score changed significantly since last fetch)
    alerts: list[TopicCard] = Field(default_factory=list)
