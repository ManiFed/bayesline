import { useMemo, useState } from "react";
import type { FeedItem, TopicCard } from "../types";
import { useFeed } from "../hooks/useFeed";
import { useTopicDetail } from "../hooks/useTopicDetail";
import StoryPage from "./StoryPage";
import NarrativesPage from "./NarrativesPage";
import MethodologyPage from "./MethodologyPage";

type Page = "home" | "narratives" | "methodology";

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return "";
  }
}

function urgencyFromScore(score: number): string {
  if (score >= 75) return "Critical";
  if (score >= 55) return "High";
  if (score >= 35) return "Medium";
  return "Low";
}

export default function App() {
  const { feed, loading, error, refresh } = useFeed();
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const { detail, loading: detailLoading } = useTopicDetail(selectedTopicId);
  const [page, setPage] = useState<Page>("home");

  const allItems = useMemo(() => {
    if (!feed) return [] as FeedItem[];
    const map = new Map<string, FeedItem>();

    feed.sections.forEach((section) => {
      section.items.forEach((item) => {
        const existing = map.get(item.card.id);
        if (!existing || item.card.impact_score > existing.card.impact_score) {
          map.set(item.card.id, item);
        }
      });
    });

    return Array.from(map.values());
  }, [feed]);

  const topStories = useMemo(
    () => [...allItems].sort((a, b) => b.card.impact_score - a.card.impact_score).slice(0, 8),
    [allItems],
  );

  const clusters = useMemo(() => {
    const grouped = new Map<string, TopicCard[]>();

    allItems.forEach((item) => {
      const key = item.card.category?.trim() || "General";
      const bucket = grouped.get(key) ?? [];
      bucket.push(item.card);
      grouped.set(key, bucket);
    });

    return Array.from(grouped.entries())
      .map(([name, stories]) => {
        const avgImpact = stories.reduce((sum, story) => sum + story.impact_score, 0) / stories.length;
        const lead = [...stories].sort((a, b) => b.impact_score - a.impact_score)[0];
        return {
          name,
          stories,
          avgImpact,
          lead,
        };
      })
      .sort((a, b) => b.avgImpact - a.avgImpact)
      .slice(0, 6);
  }, [allItems]);

  const sectionSignals = useMemo(() => {
    if (!feed) return [];

    return feed.sections
      .filter((section) => section.items.length > 0)
      .map((section) => {
        const avgImpact =
          section.items.reduce((sum, item) => sum + item.card.impact_score, 0) / section.items.length;
        const withDeadlines = section.items.filter((item) => item.card.deadlines.length > 0).length;
        return {
          name: section.display_name,
          stories: section.items.length,
          avgImpact,
          deadlineRatio: withDeadlines / section.items.length,
        };
      })
      .sort((a, b) => b.avgImpact - a.avgImpact);
  }, [feed]);

  const metrics = useMemo(() => {
    if (!topStories.length) {
      return {
        avgImpact: 0,
        criticalStories: 0,
        upcomingDeadlines: 0,
      };
    }

    const avgImpact = topStories.reduce((sum, item) => sum + item.card.impact_score, 0) / topStories.length;
    const criticalStories = topStories.filter((item) => item.card.impact_score >= 75).length;
    const upcomingDeadlines = topStories.reduce((sum, item) => sum + item.card.deadlines.length, 0);

    return { avgImpact, criticalStories, upcomingDeadlines };
  }, [topStories]);

  const lastUpdate = feed
    ? new Date(feed.generated_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : null;

  return (
    <>
      <nav className="top-nav">
        <div className="nav-left">
          <span className="nav-logo">Bayesline</span>
          <span className="nav-tagline">Newsroom driven by SIGNAL from prediction markets</span>
        </div>

        <div className="nav-center">
          <button className={`nav-link ${page === "home" ? "active" : ""}`} onClick={() => setPage("home")}>Newsroom</button>
          <button className={`nav-link ${page === "narratives" ? "active" : ""}`} onClick={() => setPage("narratives")}>Narratives</button>
          <button className={`nav-link ${page === "methodology" ? "active" : ""}`} onClick={() => setPage("methodology")}>Methodology</button>
        </div>
      </nav>

      <div className="app-content">
        {page === "home" && (
          <div className="newsroom">
            <header className="newsroom-hero">
              <div>
                <p className="newsroom-eyebrow">Live intelligence desk</p>
                <h1 className="newsroom-title">Top stories, clusters, and storyline dashboards</h1>
                <p className="newsroom-subtitle">
                  Built from market repricing and cross-source confirmation, not social-noise cycles.
                </p>
              </div>
              <div className="newsroom-status">
                <span className="live-pulse" />
                {lastUpdate ? `Desk updated ${lastUpdate}` : "Connecting to signal feed..."}
                <button className="btn" onClick={refresh}>Refresh feed</button>
              </div>
            </header>

            {loading && !feed && (
              <div className="loading">
                <div className="spinner" />
                <p style={{ marginTop: 16, fontFamily: "var(--font-mono)", fontSize: 12 }}>Scanning markets for signal...</p>
              </div>
            )}
            {error && (
              <div className="error-state">
                <p>Unable to load newsroom: {error}</p>
                <button className="btn" onClick={refresh}>Retry</button>
              </div>
            )}

            {feed && (
              <>
                <section className="signal-metrics-grid">
                  <article className="metric-card">
                    <p>Average impact (top stories)</p>
                    <strong>{metrics.avgImpact.toFixed(1)}</strong>
                  </article>
                  <article className="metric-card">
                    <p>Critical stories</p>
                    <strong>{metrics.criticalStories}</strong>
                  </article>
                  <article className="metric-card">
                    <p>Upcoming deadlines</p>
                    <strong>{metrics.upcomingDeadlines}</strong>
                  </article>
                  <article className="metric-card">
                    <p>Total monitored stories</p>
                    <strong>{feed.total_topics}</strong>
                  </article>
                </section>

                <div className="newsroom-layout">
                  <section className="top-stories-panel">
                    <div className="panel-heading">
                      <h2>Top Stories</h2>
                      <span>Ranked by ImpactScore</span>
                    </div>
                    <div className="top-stories-list">
                      {topStories.map((item) => (
                        <button key={item.card.id} className="top-story-row" onClick={() => setSelectedTopicId(item.card.id)}>
                          <div>
                            <p className="top-story-kicker">{item.card.category || "General"} · {urgencyFromScore(item.card.impact_score)}</p>
                            <h3>{item.card.title}</h3>
                            <p>{item.card.summary}</p>
                          </div>
                          <div className="top-story-meta">
                            <span>{Math.round(item.card.impact_score)}</span>
                            <small>{timeAgo(item.card.updated_at)}</small>
                          </div>
                        </button>
                      ))}
                    </div>
                  </section>

                  <aside className="dashboard-panel">
                    <div className="panel-heading">
                      <h2>Storyline Dashboard</h2>
                      <span>Signal concentration by newsroom lane</span>
                    </div>
                    <div className="signal-lanes">
                      {sectionSignals.map((lane) => (
                        <div key={lane.name} className="signal-lane">
                          <div className="signal-lane-labels">
                            <strong>{lane.name}</strong>
                            <span>{lane.stories} stories · {lane.avgImpact.toFixed(0)} avg impact</span>
                          </div>
                          <div className="signal-bar-track">
                            <div className="signal-bar-fill" style={{ width: `${Math.min(lane.avgImpact, 100)}%` }} />
                          </div>
                          <small>{Math.round(lane.deadlineRatio * 100)}% with active deadlines</small>
                        </div>
                      ))}
                    </div>
                  </aside>
                </div>

                <section className="clusters-panel">
                  <div className="panel-heading">
                    <h2>Story Clusters</h2>
                    <span>Grouped by category with strongest lead narrative</span>
                  </div>
                  <div className="clusters-grid">
                    {clusters.map((cluster) => (
                      <article key={cluster.name} className="cluster-card">
                        <div className="cluster-head">
                          <h3>{cluster.name}</h3>
                          <span>{cluster.avgImpact.toFixed(0)} impact avg</span>
                        </div>
                        <p className="cluster-lead">Lead: {cluster.lead.title}</p>
                        <ul>
                          {cluster.stories
                            .sort((a, b) => b.impact_score - a.impact_score)
                            .slice(0, 3)
                            .map((story) => (
                              <li key={story.id}>
                                <button onClick={() => setSelectedTopicId(story.id)}>{story.title}</button>
                              </li>
                            ))}
                        </ul>
                      </article>
                    ))}
                  </div>
                </section>

                {feed.alerts.length > 0 && (
                  <section className="alerts-panel">
                    <div className="panel-heading">
                      <h2>Desk Alerts</h2>
                      <span>Immediate market dislocations worth editor attention</span>
                    </div>
                    <div className="alerts-list">
                      {feed.alerts.slice(0, 4).map((alert) => (
                        <button key={alert.id} className="alert-row" onClick={() => setSelectedTopicId(alert.id)}>
                          <span>{alert.title}</span>
                          <strong>{Math.round(alert.impact_score)}</strong>
                        </button>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </div>
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
