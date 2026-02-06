"""FastAPI routes for the Bayesline news feed API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from ..models.feed import FeedResponse, UserPreferences
from ..models.topic import TopicCard, ImpactTopic
from ..services.orchestrator import Orchestrator

router = APIRouter()

# Shared orchestrator instance (initialized in main.py)
_orchestrator: Optional[Orchestrator] = None


def set_orchestrator(orch: Orchestrator) -> None:
    global _orchestrator
    _orchestrator = orch


def get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise HTTPException(503, "Service not initialized")
    return _orchestrator


# ── Feed ─────────────────────────────────────────────────────────────────

@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    geographies: Optional[str] = Query(None, description="Comma-separated geo codes"),
    sectors: Optional[str] = Query(None, description="Comma-separated sector names"),
    severity: Optional[str] = Query("balanced", description="high_only|balanced|all"),
    prefer_undercovered: bool = Query(False),
    prefer_deadlines: bool = Query(False),
):
    """Get the main news feed, organized by importance sections."""
    orch = get_orchestrator()
    prefs = UserPreferences(
        geographies=geographies.split(",") if geographies else [],
        sectors=sectors.split(",") if sectors else [],
        severity_preference=severity or "balanced",
        prefer_undercovered=prefer_undercovered,
        prefer_deadlines=prefer_deadlines,
    )
    return orch.feed_service.build_feed(prefs, page, page_size)


# ── Topics ───────────────────────────────────────────────────────────────

@router.get("/topics", response_model=list[TopicCard])
async def list_topics(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List all scored topics, optionally filtered by category."""
    orch = get_orchestrator()
    topics = orch.store.get_all_topics()

    if category:
        topics = [t for t in topics if t.category.lower() == category.lower()]

    # Sort by impact score descending
    topics.sort(key=lambda t: t.scores.impact_score, reverse=True)
    topics = topics[:limit]

    # Convert to cards (no market data)
    return [_topic_to_card(t) for t in topics]


@router.get("/topics/{topic_id}", response_model=TopicCard)
async def get_topic(topic_id: str):
    """Get a single topic's full card."""
    orch = get_orchestrator()
    topic = orch.store.get_topic(topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    return _topic_to_card(topic)


@router.get("/topics/{topic_id}/detail")
async def get_topic_detail(topic_id: str):
    """Get extended topic detail including scenarios and uncertainties."""
    orch = get_orchestrator()
    topic = orch.store.get_topic(topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")

    return {
        "id": topic.id,
        "title": topic.title,
        "category": topic.category,
        "what_happened": topic.what_happened,
        "what_matters_next": topic.what_matters_next,
        "most_likely_paths": [s.model_dump() for s in topic.most_likely_paths],
        "key_uncertainties": topic.key_uncertainties,
        "what_changed_today": topic.what_changed_today,
        "why_it_matters": topic.why_it_matters,
        "why_in_feed": topic.scores.explanation,
        "impact_score": topic.scores.impact_score,
        "deadlines": [d.model_dump() for d in topic.deadlines],
        "citations": [c.model_dump() for c in topic.citations],
        "updated_at": topic.updated_at.isoformat(),
    }


# ── System ───────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats():
    """System statistics (for monitoring)."""
    orch = get_orchestrator()
    return orch.store.stats()


@router.post("/pipeline/run")
async def trigger_pipeline():
    """Manually trigger a full pipeline run."""
    orch = get_orchestrator()
    await orch.run_full_pipeline()
    return {"status": "complete", **orch.store.stats()}


@router.post("/pipeline/quick-update")
async def trigger_quick_update():
    """Trigger a lightweight snapshot + rescore."""
    orch = get_orchestrator()
    await orch.run_quick_update()
    return {"status": "complete"}


# ── Helpers ──────────────────────────────────────────────────────────────

def _topic_to_card(topic: ImpactTopic) -> TopicCard:
    summary_parts = []
    if topic.what_happened:
        sentences = topic.what_happened.split(". ")
        summary_parts.extend(sentences[:3])
    summary = ". ".join(summary_parts).strip()
    if summary and not summary.endswith("."):
        summary += "."

    return TopicCard(
        id=topic.id,
        slug=topic.slug,
        title=topic.title,
        category=topic.category,
        summary=summary,
        what_to_watch=topic.what_matters_next[:5],
        why_it_matters=topic.why_it_matters,
        what_changed_today=topic.what_changed_today,
        deadlines=topic.deadlines,
        citations=topic.citations,
        impact_score=topic.scores.impact_score,
        why_in_feed=topic.scores.explanation,
        section="",
        updated_at=topic.updated_at,
    )
