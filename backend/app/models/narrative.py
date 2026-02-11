"""Narrative models for grouping related story clusters."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Narrative(BaseModel):
    id: str
    label: str
    description: str = ""
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    weekly_cumulative_impact: float = 0.0
    coverage_diversity: float = 0.0
    bias_spread: float = 0.0
    topic_ids: list[str] = Field(default_factory=list)


class NarrativeSummary(BaseModel):
    id: str
    label: str
    description: str
    last_updated: datetime
    weekly_cumulative_impact: float


class NarrativePoint(BaseModel):
    timestamp: datetime
    cumulative_impact: float


class NarrativeDetail(BaseModel):
    id: str
    label: str
    description: str
    last_updated: datetime
    cumulative_impact_curve: list[NarrativePoint] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)
    key_markets: list[str] = Field(default_factory=list)
    coverage_diversity: float = 0.0
    bias_spread: float = 0.0
