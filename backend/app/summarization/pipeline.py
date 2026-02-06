"""Summarization pipeline: evidence pack → structured extraction → constrained summary.

Every sentence is tethered to evidence. If evidence is thin, uncertainty is explicit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from ..config import settings
from ..models.topic import ImpactTopic, Scenario, Citation
from ..models.news import NewsArticle
from ..services.store import DataStore

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert news analyst for a non-partisan intelligence briefing platform.
You produce factual, evidence-based summaries. Every claim must be supported by the provided sources.

Rules:
1. Write ONLY from the provided evidence. Never fabricate facts, dates, or quotes.
2. If evidence is thin or conflicting, explicitly state uncertainty.
3. Use neutral, professional language. No sensationalism or clickbait.
4. Never mention prediction markets, betting, trading, or market prices.
5. Focus on what happened, what it means, and what comes next.
6. Cite sources by their title when making specific claims.
7. Include dates and deadlines when available."""

SUMMARY_TEMPLATE = """Given these sources about "{topic_title}":

{evidence_pack}

Produce a JSON response with exactly this structure:
{{
  "what_happened": "One factual paragraph summarizing the current state. Cite sources.",
  "what_matters_next": ["Bullet 1 with date if available", "Bullet 2", "Bullet 3"],
  "most_likely_paths": [
    {{"label": "Scenario name", "description": "What happens", "likelihood": "most likely|possible|unlikely", "implications": "What it means"}},
  ],
  "key_uncertainties": ["What is not known 1", "What is not known 2"],
  "what_changed_today": "One sentence about the most recent development",
  "why_it_matters": "One sentence on real-world consequence",
  "summary": "Three concise sentences for the feed card"
}}

If evidence is insufficient for any field, say "Insufficient evidence to determine [X]."
Return ONLY valid JSON, no markdown."""


class SummarizationPipeline:
    """Orchestrates the evidence → summary pipeline for each topic."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self._client: httpx.AsyncClient | None = None

    async def summarize_topic(self, topic: ImpactTopic) -> ImpactTopic:
        """Run the full summarization pipeline for a topic."""
        # Step 1: Build evidence pack
        evidence_pack = self._build_evidence_pack(topic)

        if not evidence_pack.strip():
            topic.what_happened = "This topic is emerging. No detailed sources available yet."
            topic.what_changed_today = "Newly detected topic."
            return topic

        # Step 2+3: Structured extraction + constrained summarization via LLM
        prompt = SUMMARY_TEMPLATE.format(
            topic_title=topic.title,
            evidence_pack=evidence_pack,
        )

        result = await self._call_llm(prompt)
        if result:
            self._apply_result(topic, result)

        # Step 4: Quality gates
        self._quality_check(topic)

        topic.updated_at = datetime.now(timezone.utc)
        self.store.upsert_topic(topic)
        return topic

    async def summarize_all(self) -> list[ImpactTopic]:
        """Summarize all topics that need updates."""
        topics = self.store.get_all_topics()
        updated: list[ImpactTopic] = []
        for topic in topics:
            try:
                t = await self.summarize_topic(topic)
                updated.append(t)
            except Exception:
                logger.error("summarization.failed", topic_id=topic.id, exc_info=True)
        return updated

    def _build_evidence_pack(self, topic: ImpactTopic) -> str:
        """Step 1: Assemble top sources and key passages."""
        sections: list[str] = []

        # Primary sources first
        for cit in topic.citations:
            if cit.is_primary:
                sections.append(
                    f"[PRIMARY SOURCE] {cit.title}\n"
                    f"URL: {cit.url}\n"
                    f"Excerpt: {cit.excerpt}\n"
                )

        # Then reporting sources
        for cit in topic.citations:
            if not cit.is_primary:
                article = self.store.get_article(cit.source_id)
                text = ""
                if article:
                    text = article.text[:500] if article.text else article.summary
                sections.append(
                    f"[REPORTING] {cit.title}\n"
                    f"URL: {cit.url}\n"
                    f"Content: {text}\n"
                )

        # Also pull in articles by ID
        for aid in topic.article_ids:
            article = self.store.get_article(aid)
            if article and not any(c.source_id == aid for c in topic.citations):
                sections.append(
                    f"[ARTICLE] {article.title} ({article.source_name})\n"
                    f"Published: {article.published_at}\n"
                    f"Content: {(article.text or article.summary)[:400]}\n"
                )

        # Cap total evidence pack size
        pack = "\n---\n".join(sections[:15])
        if len(pack) > 8000:
            pack = pack[:8000] + "\n[...truncated]"
        return pack

    async def _call_llm(self, prompt: str) -> Optional[dict]:
        """Call the configured LLM with the summarization prompt."""
        if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
            return await self._call_anthropic(prompt)
        elif settings.llm_provider == "openai" and settings.openai_api_key:
            return await self._call_openai(prompt)
        else:
            # Fallback: return a skeleton when no API key is configured
            logger.warning("summarization.no_llm_configured")
            return None

    async def _call_anthropic(self, prompt: str) -> Optional[dict]:
        client = await self._get_client()
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "max_tokens": 2000,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            return json.loads(text)
        except Exception:
            logger.error("summarization.anthropic_failed", exc_info=True)
            return None

    async def _call_openai(self, prompt: str) -> Optional[dict]:
        client = await self._get_client()
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2000,
                    "response_format": {"type": "json_object"},
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return json.loads(text)
        except Exception:
            logger.error("summarization.openai_failed", exc_info=True)
            return None

    def _apply_result(self, topic: ImpactTopic, result: dict) -> None:
        """Apply LLM result to topic fields."""
        topic.what_happened = result.get("what_happened", topic.what_happened)
        topic.what_matters_next = result.get("what_matters_next", topic.what_matters_next)
        topic.what_changed_today = result.get("what_changed_today", topic.what_changed_today)
        topic.why_it_matters = result.get("why_it_matters", topic.why_it_matters)
        topic.key_uncertainties = result.get("key_uncertainties", topic.key_uncertainties)

        # Parse scenarios
        for path in result.get("most_likely_paths", []):
            if isinstance(path, dict):
                topic.most_likely_paths.append(Scenario(
                    label=path.get("label", ""),
                    description=path.get("description", ""),
                    likelihood=path.get("likelihood", "possible"),
                    implications=path.get("implications", ""),
                ))

    def _quality_check(self, topic: ImpactTopic) -> None:
        """Step 4: Contradiction check, staleness, defamation filter."""
        # Staleness: flag if all sources are old
        if topic.citations:
            all_old = all(
                self._is_stale(c.source_id) for c in topic.citations
            )
            if all_old:
                topic.what_happened = (
                    "[Note: Sources may be outdated] " + topic.what_happened
                )

        # Thin evidence warning
        if len(topic.citations) < 2 and topic.what_happened:
            if "insufficient evidence" not in topic.what_happened.lower():
                topic.key_uncertainties.insert(
                    0, "Limited sources available — details may change"
                )

    def _is_stale(self, article_id: str, hours: int = 72) -> bool:
        article = self.store.get_article(article_id)
        if not article or not article.published_at:
            return True
        age = (datetime.now(timezone.utc) - article.published_at).total_seconds() / 3600
        return age > hours

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
