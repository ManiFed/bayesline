import { useState } from "react";
import { useFeed } from "../hooks/useFeed";
import { useTopicDetail } from "../hooks/useTopicDetail";
import FeedSectionComponent from "./FeedSectionComponent";
import TopicDetailPanel from "./TopicDetailPanel";

export default function App() {
  const { feed, loading, error, refresh } = useFeed();
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const { detail, loading: detailLoading } = useTopicDetail(selectedTopicId);

  return (
    <div className="app">
      <header className="header">
        <h1>Bayesline</h1>
        <p>What informed attention is tracking right now</p>
        <div className="header-meta">
          {feed && (
            <>
              <span>{feed.total_topics} topics tracked</span>
              <span>Updated {new Date(feed.generated_at).toLocaleTimeString()}</span>
            </>
          )}
        </div>
        <div className="header-actions">
          <button className="btn" onClick={refresh} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      {loading && !feed && (
        <div className="loading">
          <div className="spinner" />
          <p style={{ marginTop: 16 }}>Loading feed...</p>
        </div>
      )}

      {error && (
        <div className="error">
          <p>Failed to load feed: {error}</p>
          <button className="btn" onClick={refresh} style={{ marginTop: 12 }}>
            Retry
          </button>
        </div>
      )}

      {feed && feed.total_topics === 0 && (
        <div className="empty-state">
          <p>No topics detected yet.</p>
          <p>The pipeline is running — topics will appear as data is ingested.</p>
        </div>
      )}

      {feed &&
        feed.sections.map((section) => (
          <FeedSectionComponent
            key={section.name}
            section={section}
            onSelectTopic={setSelectedTopicId}
          />
        ))}

      {selectedTopicId && detail && (
        <TopicDetailPanel
          detail={detail}
          onClose={() => setSelectedTopicId(null)}
        />
      )}

      {selectedTopicId && detailLoading && (
        <div className="detail-overlay" onClick={() => setSelectedTopicId(null)}>
          <div className="detail-panel" onClick={(e) => e.stopPropagation()}>
            <div className="loading">
              <div className="spinner" />
              <p style={{ marginTop: 16 }}>Loading topic...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
