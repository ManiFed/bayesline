import type {
  FeedResponse,
  TopicCard,
  TopicDetail,
  NarrativeSummary,
  NarrativeDetail,
} from "../types";

const BASE = "/api/v1";

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`API error: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export async function getFeed(params?: {
  page?: number;
  page_size?: number;
  geographies?: string;
  sectors?: string;
}): Promise<FeedResponse> {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.page_size) search.set("page_size", String(params.page_size));
  if (params?.geographies) search.set("geographies", params.geographies);
  if (params?.sectors) search.set("sectors", params.sectors);
  const qs = search.toString();
  return fetchJson<FeedResponse>(`${BASE}/feed${qs ? "?" + qs : ""}`);
}

export async function getRecent(limit = 25): Promise<TopicCard[]> {
  return fetchJson<TopicCard[]>(`${BASE}/feed/recent?limit=${limit}`);
}

export async function getTrending(limit = 25): Promise<TopicCard[]> {
  return fetchJson<TopicCard[]>(`${BASE}/feed/trending?limit=${limit}`);
}

export async function getTopics(category?: string, limit?: number): Promise<TopicCard[]> {
  const search = new URLSearchParams();
  if (category) search.set("category", category);
  if (limit) search.set("limit", String(limit));
  const qs = search.toString();
  return fetchJson<TopicCard[]>(`${BASE}/topics${qs ? "?" + qs : ""}`);
}

export async function getTopicDetail(id: string): Promise<TopicDetail> {
  return fetchJson<TopicDetail>(`${BASE}/topics/${encodeURIComponent(id)}/detail`);
}

export async function getNarratives(): Promise<NarrativeSummary[]> {
  return fetchJson<NarrativeSummary[]>(`${BASE}/narratives`);
}

export async function getNarrativeDetail(id: string): Promise<NarrativeDetail> {
  return fetchJson<NarrativeDetail>(`${BASE}/narratives/${encodeURIComponent(id)}`);
}

export async function getMethodology(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`${BASE}/methodology`);
}

export async function triggerPipeline(): Promise<{ status: string }> {
  const resp = await fetch(`${BASE}/pipeline/run`, { method: "POST" });
  return resp.json();
}

export async function getStats(): Promise<Record<string, number>> {
  return fetchJson<Record<string, number>>(`${BASE}/stats`);
}
