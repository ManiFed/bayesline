"""Tests for the FastAPI endpoints."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router, set_orchestrator
from app.models.topic import ImpactTopic, TopicScores
from app.services.orchestrator import Orchestrator


def _make_test_app() -> tuple[FastAPI, Orchestrator]:
    """Create a minimal FastAPI app without lifespan (no pipeline run)."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    @test_app.get("/health")
    async def health():
        return {"status": "ok", "app": "test"}

    orch = Orchestrator()
    set_orchestrator(orch)

    # Seed test data
    now = datetime.now(timezone.utc)
    for i in range(3):
        topic = ImpactTopic(
            id=f"test-topic-{i}",
            slug=f"test-topic-{i}",
            title=f"Test Topic {i}",
            category="politics",
            what_happened=f"Topic {i} is developing. Key events are unfolding. More details soon.",
            what_changed_today="New information emerged today.",
            why_it_matters="Significant real-world implications.",
            scores=TopicScores(
                impact_score=80 - i * 20,
                market_signal=0.7,
                coverage_gap=0.3,
                expected_consequence=0.6,
                explanation="High activity from informed sources.",
                explanation_drivers=["High activity from informed sources"],
            ),
            created_at=now,
            updated_at=now,
        )
        orch.store.upsert_topic(topic)

    return test_app, orch


@pytest.fixture
def client():
    test_app, _ = _make_test_app()
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestFeedEndpoint:
    def test_get_feed(self, client):
        resp = client.get("/api/v1/feed")
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        assert data["total_topics"] == 3

    def test_feed_pagination(self, client):
        resp = client.get("/api/v1/feed?page=1&page_size=2")
        assert resp.status_code == 200

    def test_feed_with_preferences(self, client):
        resp = client.get("/api/v1/feed?geographies=US&prefer_undercovered=true")
        assert resp.status_code == 200


class TestTopicsEndpoint:
    def test_list_topics(self, client):
        resp = client.get("/api/v1/topics")
        assert resp.status_code == 200
        topics = resp.json()
        assert len(topics) == 3

    def test_list_topics_by_category(self, client):
        resp = client.get("/api/v1/topics?category=politics")
        assert resp.status_code == 200
        topics = resp.json()
        assert len(topics) == 3

    def test_get_topic(self, client):
        resp = client.get("/api/v1/topics/test-topic-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Topic 0"

    def test_get_topic_not_found(self, client):
        resp = client.get("/api/v1/topics/nonexistent")
        assert resp.status_code == 404

    def test_get_topic_detail(self, client):
        resp = client.get("/api/v1/topics/test-topic-0/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert "what_happened" in data
        assert "what_matters_next" in data
        assert "key_uncertainties" in data
        assert "impact_score" in data
        # Should not contain market references
        assert "market_ids" not in data


class TestStatsEndpoint:
    def test_stats(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert data["topics"] == 3
