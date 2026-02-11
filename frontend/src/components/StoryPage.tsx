import { useState } from "react";
import type { TopicDetail } from "../types";

function impactBadgeClass(score: number): string {
  if (score >= 60) return "impact-badge-high";
  if (score >= 30) return "impact-badge-mid";
  return "impact-badge-low";
}

function impactLabel(score: number): string {
  if (score >= 60) return "High";
  if (score >= 30) return "Medium";
  return "Low";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return "";
  }
}

function likelihoodClass(l: string): string {
  if (l.includes("most likely")) return "likelihood-most-likely";
  if (l.includes("unlikely")) return "likelihood-unlikely";
  return "likelihood-possible";
}

function extractSources(detail: TopicDetail): string {
  const sources = detail.citations
    .map((c) => {
      if (c.source_type) return c.source_type;
      try {
        const host = new URL(c.url).hostname
          .replace("www.", "")
          .split(".")[0];
        return host.charAt(0).toUpperCase() + host.slice(1);
      } catch {
        return c.title.split(" ")[0];
      }
    })
    .filter((v, i, a) => a.indexOf(v) === i)
    .slice(0, 5);

  return sources.join(" / ");
}

interface Props {
  detail: TopicDetail;
  onClose: () => void;
}

export default function StoryPage({ detail, onClose }: Props) {
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const sources = extractSources(detail);

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="story-page" onClick={(e) => e.stopPropagation()}>
        <button className="story-page-close" onClick={onClose}>
          &times;
        </button>

        {/* Header */}
        <div className="story-page-meta">
          <span className="ai-badge">AI Summary</span>
          <span
            className={`story-page-impact-badge ${impactBadgeClass(detail.impact_score)}`}
          >
            Impact: {impactLabel(detail.impact_score)} ({Math.round(detail.impact_score)})
          </span>
        </div>

        <h1 className="story-page-headline">{detail.title}</h1>

        <div className="story-page-meta">
          {sources && <span className="story-page-sources">{sources}</span>}
          <span className="story-page-time">{timeAgo(detail.updated_at)}</span>
        </div>

        <hr className="story-page-divider" />

        {/* What Happened */}
        <div className="story-section">
          <h2 className="story-section-title">What happened</h2>
          <p>{detail.what_happened}</p>
        </div>

        {detail.why_it_matters && (
          <div className="story-section">
            <h2 className="story-section-title">Why it matters</h2>
            <p>{detail.why_it_matters}</p>
          </div>
        )}

        {detail.what_changed_today && (
          <div className="story-section">
            <h2 className="story-section-title">Latest development</h2>
            <p>{detail.what_changed_today}</p>
          </div>
        )}

        {detail.what_matters_next.length > 0 && (
          <div className="story-section">
            <h2 className="story-section-title">What to watch</h2>
            <ul>
              {detail.what_matters_next.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Sources */}
        {detail.citations.length > 0 && (
          <div className="story-section">
            <h2 className="story-section-title">Sources</h2>
            <ul className="citation-list">
              {detail.citations.map((cit, i) => (
                <li key={i} className="citation-item">
                  <div className="citation-title">
                    {cit.url ? (
                      <a href={cit.url} target="_blank" rel="noopener noreferrer">
                        {cit.title}
                      </a>
                    ) : (
                      cit.title
                    )}
                    {cit.is_primary && (
                      <span className="citation-badge">Primary</span>
                    )}
                  </div>
                  {cit.excerpt && (
                    <p className="citation-excerpt">{cit.excerpt}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <hr className="story-page-divider" />

        {/* Scenarios */}
        {detail.most_likely_paths.length > 0 && (
          <div className="story-section">
            <h2 className="story-section-title">Market-implied scenarios</h2>
            {detail.most_likely_paths.map((scenario, i) => (
              <div key={i} className="scenario-card">
                <div className="scenario-header">
                  <span className="scenario-label">{scenario.label}</span>
                  <span
                    className={`scenario-likelihood ${likelihoodClass(scenario.likelihood)}`}
                  >
                    {scenario.likelihood}
                  </span>
                </div>
                <p className="scenario-desc">{scenario.description}</p>
                {scenario.implications && (
                  <p className="scenario-desc" style={{ marginTop: 6, opacity: 0.8 }}>
                    {scenario.implications}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Key uncertainties */}
        {detail.key_uncertainties.length > 0 && (
          <div className="story-section">
            <h2 className="story-section-title">Key uncertainties</h2>
            <ul>
              {detail.key_uncertainties.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Deadlines */}
        {detail.deadlines.length > 0 && (
          <div className="story-section">
            <h2 className="story-section-title">Upcoming deadlines</h2>
            <ul className="deadline-list">
              {detail.deadlines.map((dl, i) => (
                <li key={i} className="deadline-item">
                  <span className="deadline-date">{formatDate(dl.date)}</span>
                  <span>{dl.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <hr className="story-page-divider" />

        {/* ImpactScore Breakdown */}
        <div className="story-section">
          <div className="impact-breakdown">
            <button
              className="impact-breakdown-toggle"
              onClick={() => setBreakdownOpen(!breakdownOpen)}
            >
              <span>ImpactScore breakdown</span>
              <span>{breakdownOpen ? "\u25B2" : "\u25BC"}</span>
            </button>
            {breakdownOpen && (
              <div className="impact-breakdown-content">
                <div className="impact-factor">
                  <span className="impact-factor-label">Overall ImpactScore</span>
                  <span className="impact-factor-value">
                    {Math.round(detail.impact_score)}
                  </span>
                </div>
                <div className="impact-factor">
                  <span className="impact-factor-label">Impact level</span>
                  <span className="impact-factor-value">
                    {impactLabel(detail.impact_score)}
                  </span>
                </div>
                <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8, lineHeight: 1.6, fontFamily: "var(--font-mono)" }}>
                  ImpactScore blends story-layer quality (reporting, newsworthiness,
                  source diversity) with market-evidence signals (post-publication
                  reaction, cross-market confirmation, liquidity-weighted repricing).
                  Penalties for manipulation risk, hype gap, and market triviality
                  are applied before final scoring.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
