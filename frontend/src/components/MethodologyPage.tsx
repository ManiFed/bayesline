import { useEffect, useState } from "react";
import { getMethodology } from "../services/api";

export default function MethodologyPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    getMethodology().then(setData).catch(() => setData(null));
  }, []);

  return (
    <div className="page-block">
      <h1 className="page-title">Methodology</h1>
      <p className="page-subtitle">
        How Bayesline discovers, scores, and surfaces stories using prediction market signals and AI.
      </p>

      <div className="methodology-section">
        <h2>The Pipeline</h2>
        <p>
          Bayesline runs a continuous pipeline that ingests data from three prediction market venues
          (Polymarket, Manifold Markets, Kalshi), clusters related markets into topics using entity
          extraction and similarity scoring, then ranks every topic using a multi-layered ImpactScore.
          AI summarization produces the final narrative you read in the feed.
        </p>
      </div>

      <div className="methodology-section">
        <h2>ImpactScore v2</h2>
        <p>
          Each topic receives a composite score from 0-100 that blends two layers equally:
        </p>

        <h3>Story Layer (50%)</h3>
        <div className="methodology-weight-grid">
          <div className="methodology-weight">
            <span className="methodology-weight-label">Story quality</span>
            <span className="methodology-weight-value">0.35</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Newsworthiness</span>
            <span className="methodology-weight-value">0.40</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Coverage diversity</span>
            <span className="methodology-weight-value">0.25</span>
          </div>
        </div>

        <h3>Market Evidence Layer (50%)</h3>
        <div className="methodology-weight-grid">
          <div className="methodology-weight">
            <span className="methodology-weight-label">Story-market relevance</span>
            <span className="methodology-weight-value">0.30</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Post-publication reaction</span>
            <span className="methodology-weight-value">0.40</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Cross-market confirmation</span>
            <span className="methodology-weight-value">0.30</span>
          </div>
        </div>

        <h3>Boosts &amp; Penalties</h3>
        <div className="methodology-weight-grid">
          <div className="methodology-weight">
            <span className="methodology-weight-label">Consequence</span>
            <span className="methodology-weight-value">+0.15</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Time sensitivity</span>
            <span className="methodology-weight-value">+0.10</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Coverage gap</span>
            <span className="methodology-weight-value">+0.08</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Manipulation risk</span>
            <span className="methodology-weight-value">-0.18</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Hype gap</span>
            <span className="methodology-weight-value">-0.10</span>
          </div>
          <div className="methodology-weight">
            <span className="methodology-weight-label">Market triviality</span>
            <span className="methodology-weight-value">-0.35</span>
          </div>
        </div>
      </div>

      <div className="methodology-section">
        <h2>Feed Sections</h2>
        <p>
          Topics are sorted into four feed sections based on their signal characteristics:
        </p>
        <ul className="methodology-filter-list">
          <li><strong>Breaking Importance</strong> — Highest ImpactScore stories with confirmed market reactions in the last 24 hours.</li>
          <li><strong>Undercovered</strong> — High CoverageGap: informed traders are paying attention but news editors aren't.</li>
          <li><strong>Deadlines</strong> — Topics with upcoming resolution dates that create time-sensitive risk.</li>
          <li><strong>Slow Burn</strong> — Narratives with steady cumulative impact over 14+ days, high consequence but low recent volatility.</li>
        </ul>
      </div>

      <div className="methodology-section">
        <h2>Eligibility Gates</h2>
        <p>
          Not every market signal makes it to the feed. Topics must pass several quality filters:
        </p>
        <ul className="methodology-filter-list">
          <li>Mapping confidence between story and markets must be at least 0.45</li>
          <li>At least one article published within the last 48 hours</li>
          <li>Story cluster must be approved (public eligibility gate)</li>
          <li>Market taxonomy cannot be novelty/gambling, sports, or lottery</li>
          <li>Minimum consequence floor of 0.3 for real-world impact</li>
        </ul>
      </div>

      <div className="methodology-section">
        <h2>AI Summarization</h2>
        <p>
          Each topic's narrative is generated by Claude using a constrained evidence-pack approach.
          The LLM receives only verified source material and is instructed to write from evidence only,
          state uncertainty explicitly, and never fabricate claims. Output is structured into
          what-happened, why-it-matters, scenarios, and key uncertainties.
        </p>
        <span className="ai-badge">Powered by Claude</span>
      </div>

      {data && (
        <div className="methodology-section">
          <h2>Raw Configuration</h2>
          <pre className="methodology-block">{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
