import type { TopicCard } from "../types";

function impactLevel(score: number): "high" | "medium" | "low" {
  if (score >= 60) return "high";
  if (score >= 30) return "medium";
  return "low";
}

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "now";
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h`;
    const days = Math.floor(hours / 24);
    return `${days}d`;
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

  return sources.join(" / ");
}

interface Props {
  card: TopicCard;
  onClick: () => void;
}

export default function StoryCardComponent({ card, onClick }: Props) {
  const sources = extractSources(card);
  const level = impactLevel(card.impact_score);
  const fillWidth = Math.min(Math.max(card.impact_score, 0), 100);
  const score = Math.round(card.impact_score);

  return (
    <div className="story-card" onClick={onClick}>
      <div className="story-card-top">
        {card.category && <span className="story-category">{card.category}</span>}
        <span className="story-time">{timeAgo(card.updated_at)}</span>
      </div>

      <h3 className="story-headline">{card.title}</h3>

      {sources && <div className="story-sources">{sources}</div>}

      {card.summary && <p className="story-summary">{card.summary}</p>}

      <div className="story-impact-row">
        <span className="impact-label">Impact</span>
        <div className="impact-bar-track">
          <div
            className="impact-bar-fill"
            data-level={level}
            style={{ width: `${fillWidth}%` }}
          />
          <div className="impact-tooltip">
            ImpactScore {score}/100
          </div>
        </div>
        <span className="impact-score-num" data-level={level}>{score}</span>
      </div>

      {card.what_changed_today && (
        <p className="story-market-snippet">{card.what_changed_today}</p>
      )}
    </div>
  );
}
