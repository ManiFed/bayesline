import type { TopicCard } from "../types";

function impactLevel(score: number): string {
  if (score >= 60) return "High";
  if (score >= 30) return "Medium";
  return "Low";
}

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `Published ${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `Published ${days}d ago`;
  } catch {
    return "";
  }
}

function extractSources(card: TopicCard): string {
  const sources = card.citations
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
    .slice(0, 4);

  return sources.join(" \u2022 ");
}

interface Props {
  card: TopicCard;
  onClick: () => void;
}

export default function StoryCardComponent({ card, onClick }: Props) {
  const sources = extractSources(card);
  const level = impactLevel(card.impact_score);
  const fillWidth = Math.min(Math.max(card.impact_score, 0), 100);

  return (
    <div className="story-card" onClick={onClick}>
      {/* Headline */}
      <h3 className="story-headline">{card.title}</h3>

      {/* Source line */}
      {sources && <div className="story-sources">{sources}</div>}

      {/* Summary */}
      {card.summary && <p className="story-summary">{card.summary}</p>}

      {/* Impact bar */}
      <div className="story-impact-row">
        <span className="impact-label">Market Impact</span>
        <div className="impact-bar-track">
          <div
            className="impact-bar-fill"
            style={{ width: `${fillWidth}%` }}
          />
          <div className="impact-tooltip">
            ImpactScore: {Math.round(card.impact_score)}
          </div>
        </div>
        <span className="impact-level">{level}</span>
      </div>

      {/* Market reaction snippet */}
      {card.what_changed_today && (
        <p className="story-market-snippet">{card.what_changed_today}</p>
      )}

      {/* Timestamp */}
      <span className="story-time">{timeAgo(card.updated_at)}</span>
    </div>
  );
}
