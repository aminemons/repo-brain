import { Archive, ChevronRight, GitBranch, Github, LoaderCircle, LockKeyhole, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getGitHubRepositories, type GitHubRepository } from "../api/github";
import type { Bot } from "../api/bots";

const PAGE_SIZE = 30;

export function GitHubRepositoryPicker({
  bots,
  onSelect
}: {
  bots: Bot[];
  onSelect: (repository: GitHubRepository, existingBotId: string | null) => void;
}) {
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [account, setAccount] = useState<string | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const requestRevisionRef = useRef(0);

  const loadPage = useCallback(async (page: number, replace: boolean) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const revision = ++requestRevisionRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getGitHubRepositories(page, PAGE_SIZE, controller.signal);
      if (controller.signal.aborted || revision !== requestRevisionRef.current) return;
      setConfigured(result.configured);
      setAccount(result.account);
      setNextPage(result.next_page);
      setRepositories((current) => {
        if (replace) return result.repositories;
        const knownNames = new Set(current.map((repository) => repository.full_name));
        return [...current, ...result.repositories.filter((repository) => !knownNames.has(repository.full_name))];
      });
    } catch (loadError) {
      if (!controller.signal.aborted && revision === requestRevisionRef.current) {
        setError(loadError instanceof Error ? loadError.message : "Could not load GitHub repositories.");
      }
    } finally {
      if (!controller.signal.aborted && revision === requestRevisionRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPage(1, true);
    return () => requestRef.current?.abort();
  }, [loadPage]);

  const filteredRepositories = useMemo(() => {
    const query = filter.trim().toLocaleLowerCase();
    if (!query) return repositories;
    return repositories.filter((repository) => [
      repository.full_name,
      repository.name,
      repository.language,
      repository.default_branch
    ].some((value) => value?.toLocaleLowerCase().includes(query)));
  }, [filter, repositories]);

  const existingBotId = (repository: GitHubRepository) => repository.bot_id ??
    bots.find((bot) => repository.repo_id !== null && bot.repo_id === repository.repo_id)?.id ?? null;

  return (
    <section className="bot-github-picker" aria-label="GitHub repository picker" aria-busy={loading}>
      <header className="bot-github-picker-heading">
        <span className="bot-github-mark"><Github size={16} aria-hidden="true" /></span>
        <span><strong>Choose from GitHub</strong><small>{account ? `Connected as ${account}` : "Browse repositories from your connected account"}</small></span>
        {loading ? <LoaderCircle size={15} className="bot-github-spinner" aria-label="Loading GitHub repositories" /> : null}
      </header>

      {configured === false ? (
        <div className="bot-github-state">
          <strong>GitHub is not connected</strong>
          <p>Ask your Repo Brain administrator to set <code>GH_TOKEN</code> in the app server environment. The token stays on the server; there is no browser token field.</p>
        </div>
      ) : null}

      {configured !== false && repositories.length > 0 ? (
        <label className="bot-github-filter">
          <Search size={14} aria-hidden="true" />
          <input
            aria-label="Filter loaded GitHub repositories"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter loaded repositories"
          />
          <span>{filteredRepositories.length}/{repositories.length}</span>
        </label>
      ) : null}

      {error ? (
        <div className="bot-github-state is-error" role="alert">
          <span>{error}</span>
          <button type="button" className="bot-github-retry" onClick={() => void loadPage(repositories.length ? (nextPage ?? 1) : 1, repositories.length > 0)}>
            <RefreshCw size={13} />Retry
          </button>
        </div>
      ) : null}

      {configured !== false && loading && repositories.length === 0 ? <div className="bot-github-state" role="status">Loading repositories…</div> : null}

      {configured !== false && !loading && !error && repositories.length === 0 ? (
        <div className="bot-github-state"><strong>No repositories found</strong><p>Try adding a local folder or Git URL below.</p></div>
      ) : null}

      {filteredRepositories.length > 0 ? (
        <ul className="bot-github-repository-list" aria-label="GitHub repositories">
          {filteredRepositories.map((repository) => {
            const botId = existingBotId(repository);
            return (
              <li key={repository.full_name}>
                <button
                  type="button"
                  className="bot-github-repository"
                  onClick={() => onSelect(repository, botId)}
                  aria-label={botId ? `Open bot for ${repository.full_name}` : `Select ${repository.full_name}`}
                >
                  <span className="bot-github-repo-main">
                    <span className="bot-github-repo-title"><strong>{repository.full_name}</strong>{repository.private ? <span className="bot-github-badge"><LockKeyhole size={11} />Private</span> : null}{repository.archived ? <span className="bot-github-badge is-archived"><Archive size={11} />Archived</span> : null}</span>
                    <span className="bot-github-repo-meta">
                      {repository.language ? <span>{repository.language}</span> : null}
                      {repository.default_branch ? <span><GitBranch size={11} />{repository.default_branch}</span> : null}
                      {botId ? <span className="is-connected">Bot already exists</span> : repository.repo_id ? <span>Repository already added</span> : null}
                    </span>
                  </span>
                  <span className="bot-github-repo-action">{botId ? "Open bot" : "Select"}<ChevronRight size={14} aria-hidden="true" /></span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      {configured !== false && repositories.length > 0 && filteredRepositories.length === 0 ? (
        <div className="bot-github-state">No loaded repositories match “{filter.trim()}”.</div>
      ) : null}

      {nextPage !== null && configured !== false ? (
        <button type="button" className="bot-github-load-more" disabled={loading} onClick={() => void loadPage(nextPage, false)}>
          {loading ? <LoaderCircle size={13} className="bot-github-spinner" /> : null}
          {loading ? "Loading…" : "Load more repositories"}
        </button>
      ) : null}
    </section>
  );
}
