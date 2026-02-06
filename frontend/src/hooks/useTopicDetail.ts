import { useState, useEffect } from "react";
import type { TopicDetail } from "../types";
import { getTopicDetail } from "../services/api";

export function useTopicDetail(topicId: string | null) {
  const [detail, setDetail] = useState<TopicDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!topicId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    getTopicDetail(topicId)
      .then(setDetail)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load topic")
      )
      .finally(() => setLoading(false));
  }, [topicId]);

  return { detail, loading, error };
}
