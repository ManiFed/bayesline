import { useEffect, useState } from "react";
import { getNarratives, getNarrativeDetail } from "../services/api";
import type { NarrativeSummary, NarrativeDetail } from "../types";

export default function NarrativesPage() {
  const [items, setItems] = useState<NarrativeSummary[]>([]);
  const [selected, setSelected] = useState<NarrativeDetail | null>(null);

  useEffect(() => {
    getNarratives().then(setItems).catch(() => setItems([]));
  }, []);

  async function openNarrative(id: string) {
    const detail = await getNarrativeDetail(id);
    setSelected(detail);
  }

  return (
    <div className="page-block">
      <h1 className="page-title">Narratives</h1>
      <p className="page-subtitle">Story timelines with cumulative impact and key reacting markets.</p>
      <div className="narrative-grid">
        <div>
          {items.map((n) => (
            <button className="narrative-card" key={n.id} onClick={() => openNarrative(n.id)}>
              <h3>{n.label}</h3>
              <p>{n.description}</p>
              <small>Weekly impact: {n.weekly_cumulative_impact.toFixed(1)}</small>
            </button>
          ))}
        </div>
        {selected && (
          <div className="narrative-detail">
            <h2>{selected.label}</h2>
            <p>{selected.description}</p>
            <p>Coverage diversity: {(selected.coverage_diversity * 100).toFixed(0)}%</p>
            <p>Bias spread: {(selected.bias_spread * 100).toFixed(0)}%</p>
            <h4>Key markets</h4>
            <ul>
              {selected.key_markets.map((m) => <li key={m}>{m}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
