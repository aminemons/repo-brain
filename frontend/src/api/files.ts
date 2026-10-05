import { API_BASE, apiFetch, readJson } from "./http";
import type { RepoFilesResponse } from "./types";

export async function getRepoFiles(repoId: string): Promise<RepoFilesResponse> {
  const response = await apiFetch(`${API_BASE}/repos/${encodeURIComponent(repoId)}/files`);
  return readJson(response, "Repository files");
}
