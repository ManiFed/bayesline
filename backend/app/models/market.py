"""Prediction-market data models (internal only — never exposed to users)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MarketVenue(str, Enum):
    POLYMARKET = "polymarket"
    MANIFOLD = "manifold"
    METACULUS = "metaculus"
    KALSHI = "kalshi"


class MarketStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class Market(BaseModel):
    """A single prediction-market question across any venue."""

    id: str
    venue: MarketVenue
    venue_id: str
    question: str
    description: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)

    created_at: datetime
    close_date: Optional[datetime] = None
    resolution_date: Optional[datetime] = None
    resolved_value: Optional[float] = None
    status: MarketStatus = MarketStatus.ACTIVE

    # Current snapshot
    current_probability: Optional[float] = None
    volume_usd: float = 0.0
    open_interest_usd: float = 0.0
    num_traders: int = 0
    liquidity_usd: float = 0.0

    # Quality metadata
    resolution_source: str = ""
    has_clear_resolution: bool = True
    edit_count: int = 0
    dispute_count: int = 0

    # Entity links (extracted from question text)
    entity_ids: list[str] = Field(default_factory=list)


class MarketSnapshot(BaseModel):
    """A point-in-time snapshot of market state for time-series storage."""

    market_id: str
    timestamp: datetime
    probability: Optional[float] = None
    volume_usd: float = 0.0
    open_interest_usd: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None
    num_traders: int = 0
    liquidity_usd: float = 0.0


class MarketSignals(BaseModel):
    """Computed signals for a single market over a window (Step 1)."""

    market_id: str
    window_hours: int = 24

    # Attention signals (normalized 0-1)
    volume_norm: float = 0.0          # V_m
    open_interest_norm: float = 0.0   # O_m
    depth_norm: float = 0.0           # D_m

    # Information arrival (normalized 0-1)
    price_change: float = 0.0         # ΔP_m
    jump_score: float = 0.0           # J_m
    realized_volatility: float = 0.0  # σ_m

    # Time sensitivity
    time_to_resolution: float = 0.0   # T_m

    # Quality controls (normalized 0-1)
    quality_score: float = 0.5        # Q_m
    robustness_score: float = 0.5     # R_m

    # Composites
    activity_composite: float = 0.0   # A_m
    market_signal: float = 0.0        # S_m

    computed_at: datetime = Field(default_factory=datetime.utcnow)
