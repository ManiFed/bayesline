export interface Citation {
  source_id: string;
  source_type: string;
  title: string;
  url: string;
  excerpt: string;
  is_primary: boolean;
}

export interface Deadline {
  date: string;
  description: string;
  source: string;
}

export interface Scenario {
  label: string;
  description: string;
  likelihood: string;
  implications: string;
}

export interface TopicCard {
  id: string;
  slug: string;
  title: string;
  category: string;
  summary: string;
  what_to_watch: string[];
  why_it_matters: string;
  what_changed_today: string;
  deadlines: Deadline[];
  citations: Citation[];
  impact_score: number;
  why_in_feed: string;
  section: string;
  updated_at: string;
}

export interface TopicDetail {
  id: string;
  title: string;
  category: string;
  what_happened: string;
  what_matters_next: string[];
  most_likely_paths: Scenario[];
  key_uncertainties: string[];
  what_changed_today: string;
  why_it_matters: string;
  why_in_feed: string;
  impact_score: number;
  deadlines: Deadline[];
  citations: Citation[];
  updated_at: string;
  reaction_events?: ReactionEvent[];
}

export interface ReactionEvent {
  market_id: string;
  reaction_start_time: string;
  peak_move_time: string;
  peak_magnitude: number;
  persistence_minutes: number;
  reversal_magnitude: number;
  implied_surprise: number;
  moved_pre_story: boolean;
  confirmed: boolean;
}

export interface FeedItem {
  card: TopicCard;
  position: number;
  section: string;
  personalization_boost: number;
}

export interface FeedSection {
  name: string;
  display_name: string;
  description: string;
  items: FeedItem[];
}

export interface FeedResponse {
  sections: FeedSection[];
  total_topics: number;
  generated_at: string;
  page: number;
  page_size: number;
  alerts: TopicCard[];
}

export interface UserPreferences {
  geographies: string[];
  sectors: string[];
  severity_preference: string;
  prefer_undercovered: boolean;
  prefer_deadlines: boolean;
}


export interface NarrativeSummary {
  id: string;
  label: string;
  description: string;
  last_updated: string;
  weekly_cumulative_impact: number;
}

export interface NarrativePoint {
  timestamp: string;
  cumulative_impact: number;
}

export interface NarrativeDetail {
  id: string;
  label: string;
  description: string;
  last_updated: string;
  cumulative_impact_curve: NarrativePoint[];
  topic_ids: string[];
  key_markets: string[];
  coverage_diversity: number;
  bias_spread: number;
}
