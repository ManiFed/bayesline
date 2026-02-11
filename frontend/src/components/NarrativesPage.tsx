import { useEffect, useState } from "react";
import { getNarratives, getNarrativeDetail } from "../services/api";
import type { NarrativeSummary, NarrativeDetail } from "../types";

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return "Updated just now";
    if (hours < 24) return `Updated ${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `Updated ${days}d ago`;
  } catch {
    return "";
  }
}

export default function NarrativesPage() {
  const [items, setItems] = useState<NarrativeSummary[]>([]);
  const [selected, setSelected] = useState<NarrativeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getNarratives()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  async function openNarrative(id: string) {
    const detail = await getNarrativeDetail(id);
    setSelected(detail);
  }

  return (
    <div className="page-block">
      <h1 className="page-title">Narratives</h1>
      <p className="page-subtitle">
        Multi-topic story arcs tracked over time. Each narrative groups related topics and
        measures cumulative impact across prediction markets.
      </p>

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p style={{ marginTop: 16, fontFamily: "var(--font-mono)", fontSize: 12 }}>Loading narratives...</p>
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="empty-state">
          <p>No narratives detected yet.</p>
          <p>Narratives emerge when multiple topics share common real-world story arcs.</p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="narrative-grid">
          <div className="narrative-list">
            {items.map((n) => (
              <button
                className="narrative-card"
                key={n.id}
                onClick={() => openNarrative(n.id)}
              >
                <h3>{n.label}</h3>
                <p>{n.description}</p>
                <small>
                  Weekly impact: <span className="narrative-impact-value">{n.weekly_cumulative_impact.toFixed(1)}</span>
                  {" "}&middot;{" "}
                  {timeAgo(n.last_updated)}
                </small>
              </button>
            ))}
          </div>
          {selected && (
            <div className="narrative-detail">
              <h2>{selected.label}</h2>
              <p>{selected.description}</p>

              <div className="narrative-stat-row">
                <div className="narrative-stat">
                  <span className="narrative-stat-label">Coverage diversity</span>
                  <span className="narrative-stat-value">{(selected.coverage_diversity * 100).toFixed(0)}%</span>
                </div>
                <div className="narrative-stat">
                  <span className="narrative-stat-label">Bias spread</span>
                  <span className="narrative-stat-value">{(selected.bias_spread * 100).toFixed(0)}%</span>
                </div>
                <div className="narrative-stat">
                  <span className="narrative-stat-label">Topics</span>
                  <span className="narrative-stat-value">{selected.topic_ids.length}</span>
                </div>
              </div>

              {selected.key_markets.length > 0 && (
                <>
                  <h4>Key reacting markets</h4>
                  <ul>
                    {selected.key_markets.map((m) => <li key={m}>{m}</li>)}
                  </ul>
                </>
              )}

              {selected.cumulative_impact_curve.length > 0 && (
                <>
                  <h4>Impact timeline</h4>
                  <div style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 60, marginTop: 8 }}>
                    {selected.cumulative_impact_curve.map((point, i) => {
                      const maxVal = Math.max(...selected.cumulative_impact_curve.map(p => p.cumulative_impact), 1);
                      const height = (point.cumulative_impact / maxVal) * 100;
                      return (
                        <div
                          key={i}
                          title={`${new Date(point.timestamp).toLocaleDateString()}: ${point.cumulative_impact.toFixed(1)}`}
                          style={{
                            flex: 1,
                            height: `${height}%`,
                            minHeight: 2,
                            background: "var(--color-undercovered)",
                            borderRadius: 2,
                            opacity: 0.4 + (i / selected.cumulative_impact_curve.length) * 0.6,
                          }}
                        />
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
