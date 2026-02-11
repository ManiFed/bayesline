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

  return (
    <>
      <nav className="top-nav">
        <div className="nav-left">
          <span className="nav-logo">Bayesline</span>
          <span className="nav-tagline">Story-first market reaction intelligence</span>
        </div>

        <div className="nav-center">
          <button className={`nav-link ${page === "home" ? "active" : ""}`} onClick={() => setPage("home")}>Home</button>
          <button className={`nav-link ${page === "narratives" ? "active" : ""}`} onClick={() => setPage("narratives")}>Narratives</button>
          <button className={`nav-link ${page === "methodology" ? "active" : ""}`} onClick={() => setPage("methodology")}>Methodology</button>
        </div>
      </nav>

      <div className="app-content">
        {page === "home" && (
          <>
            <div className="page-header">
              <div className="page-header-row">
                <h1 className="page-title">Today's most impactful stories</h1>
                {lastUpdate && (
                  <span className="page-updated">Updated continuously • Last update {lastUpdate}</span>
                )}
              </div>
            </div>

            {loading && !feed && (
              <div className="loading"><div className="spinner" /><p style={{ marginTop: 16 }}>Loading stories...</p></div>
            )}
            {error && (
              <div className="error-state"><p>Unable to load stories: {error}</p><button className="btn" onClick={refresh}>Try again</button></div>
            )}
            {feed && feed.total_topics === 0 && (
              <div className="empty-state"><p>No stories yet.</p><p>Stories appear when approved reporting is ingested and scored.</p></div>
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
            <div className="loading"><div className="spinner" /><p style={{ marginTop: 16 }}>Loading story...</p></div>
          </div>
        </div>
      )}
    </>
  );
}
