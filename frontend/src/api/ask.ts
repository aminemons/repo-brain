import { API_BASE, apiFetch, readJson } from "./http";
import type { AskResponse } from "./types";

export async function askRepo(repoId: string, question: string, signal?: AbortSignal): Promise<AskResponse> {
  const response = await apiFetch(`${API_BASE}/repos/${encodeURIComponent(repoId)}/ask`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      question,
      mode: "graph_rag",
      max_hops: 2,
      include_sources: true,
      include_graph: true
    })
  });
  return readJson(response, "Ask");
}
