"""News and primary-source data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    NEWS_ARTICLE = "news_article"
    WIRE_SERVICE = "wire_service"
    LEGISLATION = "legislation"
    REGULATORY_DOCKET = "regulatory_docket"
    COURT_FILING = "court_filing"
    CORPORATE_FILING = "corporate_filing"
    GOVERNMENT_STATEMENT = "government_statement"
    CENTRAL_BANK = "central_bank"
    DISASTER_BULLETIN = "disaster_bulletin"
    SOCIAL_MEDIA = "social_media"
    EXPERT_ANALYSIS = "expert_analysis"


class NewsArticle(BaseModel):
    """A news article from any publisher or wire service."""

    id: str
    url: str
    title: str
    text: str = ""
    summary: str = ""
    source_name: str = ""
    source_type: SourceType = SourceType.NEWS_ARTICLE
    authors: list[str] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    # Prominence indicators
    is_front_page: bool = False
    section: str = ""
    prominence_score: float = 0.0  # 0-1: how prominently featured

    # Entity links
    entity_ids: list[str] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)

    # Deduplication
    content_hash: str = ""
    cluster_id: Optional[str] = None


class PrimarySource(BaseModel):
    """A primary document (legislation, filing, ruling, etc.)."""

    id: str
    source_type: SourceType
    title: str
    url: str = ""
    identifier: str = ""  # bill number, docket number, case number
    text: str = ""
    summary: str = ""
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    # Structured metadata
    jurisdiction: str = ""
    status: str = ""  # pending, passed, filed, delayed
    next_date: Optional[datetime] = None
    stakeholders: list[str] = Field(default_factory=list)

    entity_ids: list[str] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)
