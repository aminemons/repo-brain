import { API_BASE, apiFetch, readJson } from "./http";
import type { GraphResponse, GraphStatusResponse } from "./types";

export async function getRepoGraph(repoId: string): Promise<GraphResponse> {
  const response = await apiFetch(`${API_BASE}/repos/${encodeURIComponent(repoId)}/graph`);
  return readJson(response, "Repository graph");
}

export async function getRepoGraphStatus(repoId: string): Promise<GraphStatusResponse> {
  const response = await apiFetch(`${API_BASE}/repos/${encodeURIComponent(repoId)}/graph/status`);
  return readJson(response, "Repository graph status");
}
