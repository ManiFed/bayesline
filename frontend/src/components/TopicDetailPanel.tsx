import type { TopicDetail } from "../types";

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

function likelihoodClass(l: string): string {
  if (l.includes("most likely")) return "likelihood-most-likely";
  if (l.includes("unlikely")) return "likelihood-unlikely";
  return "likelihood-possible";
}

interface Props {
  detail: TopicDetail;
  onClose: () => void;
}

export default function TopicDetailPanel({ detail, onClose }: Props) {
  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={(e) => e.stopPropagation()}>
        <button className="detail-close" onClick={onClose}>
          &times;
        </button>

        <h2 className="detail-title">{detail.title}</h2>
        <span className="card-category">{detail.category}</span>

        {/* What Happened */}
        <div className="detail-section">
          <h3>What Happened</h3>
          <p>{detail.what_happened}</p>
        </div>

        {/* Why It Matters */}
        {detail.why_it_matters && (
          <div className="detail-section">
            <h3>Why It Matters</h3>
            <p>{detail.why_it_matters}</p>
          </div>
        )}

        {/* What Changed Today */}
        {detail.what_changed_today && (
          <div className="detail-section">
            <h3>What Changed Today</h3>
            <p>{detail.what_changed_today}</p>
          </div>
        )}

        {/* What Matters Next */}
        {detail.what_matters_next.length > 0 && (
          <div className="detail-section">
            <h3>What Matters Next</h3>
            <ul>
              {detail.what_matters_next.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Most Likely Paths */}
        {detail.most_likely_paths.length > 0 && (
          <div className="detail-section">
            <h3>Most Likely Paths</h3>
            {detail.most_likely_paths.map((scenario, i) => (
              <div key={i} className="scenario-card">
                <div>
                  <span className="scenario-label">{scenario.label}</span>
                  <span
                    className={`scenario-likelihood ${likelihoodClass(scenario.likelihood)}`}
                  >
                    {scenario.likelihood}
                  </span>
                </div>
                <p className="scenario-desc">{scenario.description}</p>
                {scenario.implications && (
                  <p className="scenario-desc" style={{ marginTop: 4 }}>
                    <strong>Implications:</strong> {scenario.implications}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Key Uncertainties */}
        {detail.key_uncertainties.length > 0 && (
          <div className="detail-section">
            <h3>Key Uncertainties</h3>
            <ul>
              {detail.key_uncertainties.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Deadlines */}
        {detail.deadlines.length > 0 && (
          <div className="detail-section">
            <h3>Upcoming Deadlines</h3>
            <ul>
              {detail.deadlines.map((dl, i) => (
                <li key={i}>
                  <strong>{formatDate(dl.date)}</strong> — {dl.description}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Evidence / Citations */}
        {detail.citations.length > 0 && (
          <div className="detail-section">
            <h3>Sources &amp; Evidence</h3>
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

        {/* Why in feed */}
        <div className="detail-section">
          <h3>Why This Is in Your Feed</h3>
          <p style={{ fontStyle: "italic" }}>{detail.why_in_feed}</p>
        </div>
      </div>
    </div>
  );
}
