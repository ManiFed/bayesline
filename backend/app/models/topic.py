"""Impact Topic — the core user-facing object."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TopicScores(BaseModel):
    """All computed scores for a topic (internal + display)."""

    # Core signals (0-1)
    market_signal: float = 0.0
    news_coverage: float = 0.0
    coverage_gap: float = 0.0
    hype_gap: float = 0.0
    expected_consequence: float = 0.0
    time_sensitivity: float = 0.0
    manipulation_risk: float = 0.0
    story_layer_score: float = 0.0
    market_evidence_score: float = 0.0
    public_eligibility_score: float = 0.0
    story_market_mapping_confidence: float = 0.0
    market_triviality_penalty: float = 0.0
    narrative_coherence_boost: float = 0.0
    narrative_novelty_boost: float = 0.0

    # Final score (0-100)
    impact_score: float = 0.0

    # Human-readable explanation (no market references)
    explanation: str = ""
    explanation_drivers: list[str] = Field(default_factory=list)

    computed_at: datetime = Field(default_factory=datetime.utcnow)


class TopicMarketMapping(BaseModel):
    """Internal mapping from a topic to its underlying markets."""

    topic_id: str
    market_id: str
    relevance_weight: float = 1.0  # downweight near-duplicates
    is_primary: bool = False


class Scenario(BaseModel):
    """A possible future path for a topic."""

    label: str
    description: str
    likelihood: str  # "most likely", "possible", "unlikely"
    implications: str = ""


class Deadline(BaseModel):
    """A known upcoming date relevant to the topic."""

    date: datetime
    description: str
    source: str = ""


class Citation(BaseModel):
    """A citation to a source document."""

    source_id: str
    source_type: str
    title: str
    url: str = ""
    excerpt: str = ""
    is_primary: bool = False


class MarketReactionEvent(BaseModel):
    """Derived market reaction object for causal analysis."""

    market_id: str
    reaction_start_time: datetime
    peak_move_time: datetime
    peak_magnitude: float = 0.0
    persistence_minutes: float = 0.0
    reversal_magnitude: float = 0.0
    implied_surprise: float = 0.0
    moved_pre_story: bool = False
    confirmed: bool = False


class ImpactTopic(BaseModel):
    """The core object: a cluster connecting markets, news, and analysis."""

    id: str
    slug: str = ""
    title: str  # Neutral, not clickbait
    category: str = ""
    subcategory: str = ""

    # Structured content
    what_happened: str = ""              # One paragraph
    what_matters_next: list[str] = Field(default_factory=list)  # Bullets with dates
    most_likely_paths: list[Scenario] = Field(default_factory=list)
    key_uncertainties: list[str] = Field(default_factory=list)
    why_in_feed: str = ""                # Plain explanation (no market mention)
    what_changed_today: str = ""
    why_it_matters: str = ""             # Consequence framing, one line

    # Evidence
    citations: list[Citation] = Field(default_factory=list)

    # Deadlines
    deadlines: list[Deadline] = Field(default_factory=list)

    # Scores
    scores: TopicScores = Field(default_factory=TopicScores)

    # Story and ranking controls
    approved_story_cluster: bool = True
    eligible_for_homepage: bool = False
    market_taxonomy: str = "financial_instrument_price"
    narrative_id: str = ""
    narrative_label: str = ""
    reaction_events: list[MarketReactionEvent] = Field(default_factory=list)

    # Internal mappings (not sent to client)
    market_ids: list[str] = Field(default_factory=list)
    article_ids: list[str] = Field(default_factory=list)
    primary_source_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    first_detected_at: Optional[datetime] = None


class TopicCard(BaseModel):
    """The user-facing card shown in the feed (no market data)."""

    id: str
    slug: str = ""
    title: str
    category: str = ""

    summary: str = ""                    # Three-sentence summary
    what_to_watch: list[str] = Field(default_factory=list)  # Bullets with dates
    why_it_matters: str = ""
    what_changed_today: str = ""

    # Deadlines (real-world dates only)
    deadlines: list[Deadline] = Field(default_factory=list)

    # Citations: primary documents first, then reporting
    citations: list[Citation] = Field(default_factory=list)

    # Scores shown to users (no market references)
    impact_score: float = 0.0
    why_in_feed: str = ""

    # Feed section assignment
    section: str = ""  # breaking, undercovered, deadlines, slow_burn

    updated_at: datetime = Field(default_factory=datetime.utcnow)
