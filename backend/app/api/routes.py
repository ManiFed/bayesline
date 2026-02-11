"""FastAPI routes for Bayesline."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from ..models.feed import FeedResponse, UserPreferences
from ..models.topic import TopicCard, ImpactTopic
from ..models.narrative import NarrativeSummary, NarrativeDetail, NarrativePoint
from ..services.orchestrator import Orchestrator

router = APIRouter()
_orchestrator: Optional[Orchestrator] = None


def set_orchestrator(orch: Orchestrator) -> None:
    global _orchestrator
    _orchestrator = orch


def get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise HTTPException(503, "Service not initialized")
    return _orchestrator


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    geographies: Optional[str] = Query(None),
    sectors: Optional[str] = Query(None),
):
    """Main feed with fixed editorial ImpactScore defaults."""
    orch = get_orchestrator()
    prefs = UserPreferences(
        geographies=geographies.split(",") if geographies else [],
        sectors=sectors.split(",") if sectors else [],
    )
    return orch.feed_service.build_feed(prefs, page, page_size)


@router.get("/feed/recent", response_model=list[TopicCard])
async def recent_feed(limit: int = Query(25, ge=1, le=100)):
    orch = get_orchestrator()
    topics = [t for t in orch.store.get_all_topics() if t.eligible_for_homepage]
    topics.sort(key=lambda t: t.updated_at, reverse=True)
    return [_topic_to_card(t) for t in topics[:limit]]


@router.get("/feed/trending", response_model=list[TopicCard])
async def trending_feed(limit: int = Query(25, ge=1, le=100)):
    orch = get_orchestrator()
    topics = [t for t in orch.store.get_all_topics() if t.eligible_for_homepage]
    topics.sort(key=lambda t: t.scores.market_evidence_score, reverse=True)
    return [_topic_to_card(t) for t in topics[:limit]]


@router.get("/topics", response_model=list[TopicCard])
async def list_topics(category: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    orch = get_orchestrator()
    topics = orch.store.get_all_topics()
    if category:
        topics = [t for t in topics if t.category.lower() == category.lower()]
    topics.sort(key=lambda t: t.scores.impact_score, reverse=True)
    return [_topic_to_card(t) for t in topics[:limit]]


@router.get("/topics/{topic_id}", response_model=TopicCard)
async def get_topic(topic_id: str):
    orch = get_orchestrator()
    topic = orch.store.get_topic(topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    return _topic_to_card(topic)


@router.get("/topics/{topic_id}/detail")
async def get_topic_detail(topic_id: str):
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
        "reaction_events": [e.model_dump() for e in topic.reaction_events],
        "updated_at": topic.updated_at.isoformat(),
    }


@router.get("/narratives", response_model=list[NarrativeSummary])
async def list_narratives():
    orch = get_orchestrator()
    groups: dict[str, list[ImpactTopic]] = defaultdict(list)
    for t in orch.store.get_all_topics():
        if t.narrative_id:
            groups[t.narrative_id].append(t)
    out: list[NarrativeSummary] = []
    for nid, topics in groups.items():
        last_updated = max(t.updated_at for t in topics)
        week_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        cumulative = sum(t.scores.impact_score for t in topics if t.updated_at >= week_cutoff)
        out.append(NarrativeSummary(
            id=nid,
            label=topics[0].narrative_label or nid,
            description=f"{len(topics)} approved stories linked to this narrative.",
            last_updated=last_updated,
            weekly_cumulative_impact=cumulative,
        ))
    out.sort(key=lambda n: n.weekly_cumulative_impact, reverse=True)
    return out


@router.get("/narratives/{narrative_id}", response_model=NarrativeDetail)
async def get_narrative(narrative_id: str):
    orch = get_orchestrator()
    topics = [t for t in orch.store.get_all_topics() if t.narrative_id == narrative_id]
    if not topics:
        raise HTTPException(404, "Narrative not found")
    topics.sort(key=lambda t: t.updated_at)
    running = 0.0
    curve: list[NarrativePoint] = []
    key_markets: dict[str, int] = defaultdict(int)
    for t in topics:
        running += t.scores.impact_score
        curve.append(NarrativePoint(timestamp=t.updated_at, cumulative_impact=running))
        for ev in t.reaction_events:
            if ev.confirmed:
                key_markets[ev.market_id] += 1
    market_rank = sorted(key_markets.items(), key=lambda kv: kv[1], reverse=True)
    return NarrativeDetail(
        id=narrative_id,
        label=topics[0].narrative_label or narrative_id,
        description=f"Timeline across {len(topics)} approved story clusters.",
        last_updated=topics[-1].updated_at,
        cumulative_impact_curve=curve,
        topic_ids=[t.id for t in topics],
        key_markets=[mid for mid, _ in market_rank[:8]],
        coverage_diversity=min(len({c.source_id for t in topics for c in t.citations}) / 20, 1.0),
        bias_spread=min(len({c.source_type for t in topics for c in t.citations}) / 8, 1.0),
    )


@router.get("/methodology")
async def methodology():
    return {
        "impact_score": {
            "story_layer": [
                "story quality and coherence",
                "newsworthiness prior",
                "coverage diversity",
            ],
            "market_evidence_layer": [
                "story-market relevance",
                "post-publication reaction evidence",
                "cross-market confirmation",
            ],
            "filters": [
                "approved story cluster with at least one recent article",
                "mapping confidence threshold",
                "taxonomy penalty for novelty/gambling/sports-only markets",
            ],
        },
        "examples": [
            "Policy story with persistent post-report move and multi-domain confirmation ranks highly.",
            "Coin-flip novelty market with no article cluster is filtered from homepage eligibility.",
        ],
    }


@router.get("/stats")
async def get_stats():
    return get_orchestrator().store.stats()


@router.post("/pipeline/run")
async def trigger_pipeline():
    orch = get_orchestrator()
    await orch.run_full_pipeline()
    return {"status": "complete", **orch.store.stats()}


@router.post("/pipeline/quick-update")
async def trigger_quick_update():
    orch = get_orchestrator()
    await orch.run_quick_update()
    return {"status": "complete"}


def _topic_to_card(topic: ImpactTopic) -> TopicCard:
    summary = ""
    if topic.what_happened:
        summary = ". ".join(topic.what_happened.split(". ")[:3]).strip()
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
