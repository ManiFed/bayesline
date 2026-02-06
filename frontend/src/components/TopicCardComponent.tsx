import type { TopicCard } from "../types";

function scoreClass(score: number): string {
  if (score >= 60) return "score-high";
  if (score >= 30) return "score-mid";
  return "score-low";
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return "just now";
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return "";
  }
}

interface Props {
  card: TopicCard;
  onClick: () => void;
}

export default function TopicCardComponent({ card, onClick }: Props) {
  return (
    <div className="topic-card" onClick={onClick}>
      <div className="card-top">
        <h3 className="card-title">{card.title}</h3>
        <span className={`card-score ${scoreClass(card.impact_score)}`}>
          {Math.round(card.impact_score)}
        </span>
      </div>

      {card.category && (
        <span className="card-category">{card.category}</span>
      )}

      {card.summary && (
        <p className="card-summary">{card.summary}</p>
      )}

      {card.what_changed_today && (
        <div className="card-changed">
          <strong>Changed today: </strong>
          {card.what_changed_today}
        </div>
      )}

      {card.deadlines.length > 0 && (
        <div className="card-deadlines">
          {card.deadlines.slice(0, 3).map((dl, i) => (
            <span key={i} className="deadline-tag">
              {formatDate(dl.date)} — {dl.description}
            </span>
          ))}
        </div>
      )}

      {card.what_to_watch.length > 0 && (
        <div className="card-watch">
          <h4>What to watch</h4>
          <ul>
            {card.what_to_watch.slice(0, 3).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card-footer">
        <span className="card-why">{card.why_in_feed}</span>
        <span>{timeAgo(card.updated_at)}</span>
      </div>
    </div>
  );
}
