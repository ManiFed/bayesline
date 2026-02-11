import { useState } from "react";
import { useFeed } from "../hooks/useFeed";
import { useTopicDetail } from "../hooks/useTopicDetail";
import FeedSectionComponent from "./FeedSectionComponent";
import StoryPage from "./StoryPage";
import NarrativesPage from "./NarrativesPage";
import MethodologyPage from "./MethodologyPage";

type Page = "home" | "narratives" | "methodology";

export default function App() {
  const { feed, loading, error, refresh } = useFeed();
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const { detail, loading: detailLoading } = useTopicDetail(selectedTopicId);
  const [page, setPage] = useState<Page>("home");

  const lastUpdate = feed
    ? new Date(feed.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : null;

  const totalStories = feed ? feed.total_topics : 0;

  return (
    <>
      <nav className="top-nav">
        <div className="nav-left">
          <span className="nav-logo">Bayesline</span>
          <span className="nav-tagline">Prediction-market intelligence, distilled by AI</span>
        </div>

        <div className="nav-center">
          <button className={`nav-link ${page === "home" ? "active" : ""}`} onClick={() => setPage("home")}>Feed</button>
          <button className={`nav-link ${page === "narratives" ? "active" : ""}`} onClick={() => setPage("narratives")}>Narratives</button>
          <button className={`nav-link ${page === "methodology" ? "active" : ""}`} onClick={() => setPage("methodology")}>Methodology</button>
        </div>
      </nav>

      <div className="app-content">
        {page === "home" && (
          <>
            <div className="page-header">
              <div className="page-header-row">
                <div>
                  <h1 className="page-title">Intelligence Feed</h1>
                </div>
                <span className="page-updated">
                  <span className="live-pulse" />
                  {lastUpdate ? `Updated ${lastUpdate}` : "Connecting..."}
                  {totalStories > 0 && <>&nbsp;&middot;&nbsp;{totalStories} stories tracked</>}
                </span>
              </div>
            </div>

            {loading && !feed && (
              <div className="loading">
                <div className="spinner" />
                <p style={{ marginTop: 16, fontFamily: "var(--font-mono)", fontSize: 12 }}>Ingesting market signals...</p>
              </div>
            )}
            {error && (
              <div className="error-state">
                <p>Unable to load stories: {error}</p>
                <button className="btn" onClick={refresh}>Retry</button>
              </div>
            )}
            {feed && feed.total_topics === 0 && (
              <div className="empty-state">
                <p>No stories yet.</p>
                <p>Stories surface when prediction market activity intersects with real-world reporting.</p>
              </div>
            )}
            {feed && feed.sections.map((section) => (
              <FeedSectionComponent key={section.name} section={section} onSelectTopic={setSelectedTopicId} />
            ))}
          </>
        )}

        {page === "narratives" && <NarrativesPage />}
        {page === "methodology" && <MethodologyPage />}
      </div>

      {selectedTopicId && detail && <StoryPage detail={detail} onClose={() => setSelectedTopicId(null)} />}
      {selectedTopicId && detailLoading && (
        <div className="detail-overlay" onClick={() => setSelectedTopicId(null)}>
          <div className="story-page" onClick={(e) => e.stopPropagation()}>
            <div className="loading">
              <div className="spinner" />
              <p style={{ marginTop: 16, fontFamily: "var(--font-mono)", fontSize: 12 }}>Loading intelligence...</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
