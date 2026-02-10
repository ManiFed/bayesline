import { useState } from "react";
import { useFeed } from "../hooks/useFeed";
import { useTopicDetail } from "../hooks/useTopicDetail";
import FeedSectionComponent from "./FeedSectionComponent";
import StoryPage from "./StoryPage";

export default function App() {
  const { feed, loading, error, refresh } = useFeed();
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const { detail, loading: detailLoading } = useTopicDetail(selectedTopicId);

  const lastUpdate = feed
    ? new Date(feed.generated_at).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <>
      {/* ─── Top Navigation ─── */}
      <nav className="top-nav">
        <div className="nav-left">
          <span className="nav-logo">Bayesline</span>
          <span className="nav-tagline">Market-grounded news ranking</span>
        </div>

        <div className="nav-center">
          <span className="nav-link active">Home</span>
          <span className="nav-link">Narratives</span>
          <span className="nav-link">Topics</span>
          <span className="nav-link">Methodology</span>
        </div>

        <div className="nav-right">
          <button className="nav-search">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            Search
          </button>
          <div className="nav-profile">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
        </div>
      </nav>

      {/* ─── Main Content ─── */}
      <div className="app-content">
        {/* Page header */}
        <div className="page-header">
          <div className="page-header-row">
            <h1 className="page-title">Today's most impactful stories</h1>
            {lastUpdate && (
              <span className="page-updated">
                Updated continuously &bull; Last update {lastUpdate}
              </span>
            )}
          </div>
        </div>

        {/* Loading state */}
        {loading && !feed && (
          <div className="loading">
            <div className="spinner" />
            <p style={{ marginTop: 16 }}>Loading stories...</p>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="error-state">
            <p>Unable to load stories: {error}</p>
            <button className="btn" onClick={refresh}>
              Try again
            </button>
          </div>
        )}

        {/* Empty state */}
        {feed && feed.total_topics === 0 && (
          <div className="empty-state">
            <p>No stories yet.</p>
            <p>Stories will appear as reporting is ingested and scored.</p>
          </div>
        )}

        {/* Feed sections */}
        {feed &&
          feed.sections.map((section) => (
            <FeedSectionComponent
              key={section.name}
              section={section}
              onSelectTopic={setSelectedTopicId}
            />
          ))}
      </div>

      {/* Story detail page overlay */}
      {selectedTopicId && detail && (
        <StoryPage
          detail={detail}
          onClose={() => setSelectedTopicId(null)}
        />
      )}

      {selectedTopicId && detailLoading && (
        <div className="detail-overlay" onClick={() => setSelectedTopicId(null)}>
          <div className="story-page" onClick={(e) => e.stopPropagation()}>
            <div className="loading">
              <div className="spinner" />
              <p style={{ marginTop: 16 }}>Loading story...</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
