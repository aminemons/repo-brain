import { API_BASE, apiFetch, readJson } from "./http";

export type GitHubRepository = {
  full_name: string;
  name: string;
  url: string;
  private: boolean;
  default_branch: string;
  language: string | null;
  archived: boolean;
  repo_id: string | null;
  bot_id: string | null;
};

export type GitHubRepositoryPage = {
  configured: boolean;
  account: string | null;
  repositories: GitHubRepository[];
  next_page: number | null;
};

export async function getGitHubRepositories(
  page = 1,
  perPage = 30,
  signal?: AbortSignal
): Promise<GitHubRepositoryPage> {
  const query = new URLSearchParams({ page: String(page), per_page: String(perPage) });
  const response = await apiFetch(`${API_BASE}/github/repositories?${query}`, { signal });
  return readJson<GitHubRepositoryPage>(response, "GitHub repositories");
}
