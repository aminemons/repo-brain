import { ChevronRight, FileCode2, FolderGit2, Github, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { createBot, getBots, refreshBotKnowledge, type Bot } from "../api/bots";
import type { GitHubRepository } from "../api/github";
import { createRepo } from "../api/repos";
import { GitHubRepositoryPicker } from "../bots/GitHubRepositoryPicker";
import type { RepoSummary } from "../api/types";
import { useRepos } from "../hooks/useRepos";

type CreateStage = "idle" | "repository" | "bot" | "index";

export function BotsPage({ onOpenBot, onOpenRepos }: { onOpenBot: (botId: string) => void; onOpenRepos: () => void }) {
  const { repos, loading: reposLoading, error: reposError, refresh: refreshRepos } = useRepos({ selectedRepoId: "", onRepoChange: () => {}, autoSelect: false });
  const [bots, setBots] = useState<Bot[]>([]);
  const [loadingBots, setLoadingBots] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [repoId, setRepoId] = useState("");
  const [addRepository, setAddRepository] = useState(false);
  const [githubPickerOpen, setGithubPickerOpen] = useState(false);
  const [repoPath, setRepoPath] = useState("");
  const [repoDisplayName, setRepoDisplayName] = useState("");
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [model, setModel] = useState("gpt-5.5");
  const [creating, setCreating] = useState(false);
  const [stage, setStage] = useState<CreateStage>("idle");
  const [createError, setCreateError] = useState<string | null>(null);
  const [createdBotId, setCreatedBotId] = useState<string | null>(null);
  const [createNotice, setCreateNotice] = useState<string | null>(null);
  const createAbortRef = useRef<AbortController | null>(null);

  useEffect(() => () => createAbortRef.current?.abort(), []);

  const refresh = useCallback((signal?: AbortSignal) => {
    setLoadingBots(true);
    setLoadError(null);
    return getBots(undefined, signal)
      .then((result) => { if (!signal?.aborted) setBots(result.bots); })
      .catch((error: unknown) => {
        if (!signal?.aborted) setLoadError(error instanceof Error ? error.message : "Could not load bots.");
      })
      .finally(() => { if (!signal?.aborted) setLoadingBots(false); });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const repoById = useMemo(() => new Map(repos.map((repo) => [repo.id, repo])), [repos]);
  const occupiedRepoIds = useMemo(() => new Set(bots.map((bot) => bot.repo_id)), [bots]);
  const availableRepos = repos.filter((repo) => !occupiedRepoIds.has(repo.id));
  const groupedBots = useMemo(() => {
    const groups = new Map<string, { repo: RepoSummary | undefined; bots: Bot[] }>();
    for (const bot of bots) {
      const repo = repoById.get(bot.repo_id);
      const key = repo?.name ?? "Repository";
      const group = groups.get(key) ?? { repo, bots: [] };
      group.bots.push(bot);
      groups.set(key, group);
    }
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
  }, [bots, repoById]);

  const selectGitHubRepository = (repository: GitHubRepository, existingBotId: string | null) => {
    setGithubPickerOpen(false);
    setCreateError(null);
    if (existingBotId) {
      onOpenBot(existingBotId);
      return;
    }
    if (repository.repo_id) {
      setAddRepository(false);
      setRepoId(repository.repo_id);
      setRepoPath("");
      setRepoDisplayName("");
      return;
    }
    setRepoId("");
    setAddRepository(true);
    setRepoPath(repository.url);
    setRepoDisplayName(repository.full_name);
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (loadingBots || creating || !name.trim() || !model.trim()) return;
    if (addRepository && !repoPath.trim()) return;
    if (!addRepository && !repoId) return;

    setCreating(true);
    setStage(addRepository ? "repository" : "bot");
    setCreateError(null);
    setCreateNotice(null);
    setCreatedBotId(null);
    let selectedRepoId = repoId;
    let addedRepoName = "";
    const controller = new AbortController();
    createAbortRef.current?.abort();
    createAbortRef.current = controller;
    try {
      if (addRepository) {
        const repo = await createRepo({ path: repoPath.trim(), name: repoDisplayName.trim() || undefined }, controller.signal);
        if (controller.signal.aborted) return;
        selectedRepoId = repo.id;
        addedRepoName = repo.name;
        setRepoId(repo.id);
        setRepoPath("");
        setRepoDisplayName("");
        setAddRepository(false);
        refreshRepos();
      }

      setStage("bot");
      const bot = await createBot({
        repo_id: selectedRepoId,
        name: name.trim(),
        instructions: instructions.trim() || undefined,
        model: model.trim()
      }, controller.signal);
      if (controller.signal.aborted) return;
      setBots((existing) => [bot, ...existing]);
      setCreatedBotId(bot.id);
      setName("");
      setInstructions("");

      setStage("index");
      setCreateNotice("Bot created. Preparing its code and documentation index…");
      try {
        await refreshBotKnowledge(bot.id, controller.signal);
        if (controller.signal.aborted) return;
        onOpenBot(bot.id);
      } catch (refreshError) {
        if (controller.signal.aborted) return;
        setCreateError(`The bot was created, but its first knowledge refresh failed. Open the bot and retry Refresh knowledge. ${refreshError instanceof Error ? refreshError.message : ""}`.trim());
        setCreateNotice(null);
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      const failure = error instanceof Error ? error.message : "Could not create the bot.";
      setCreateError(addedRepoName
        ? `Repository “${addedRepoName}” was added, but bot creation failed. It is selected below, so you can retry without adding the repository again. ${failure}`
        : failure);
      if (addRepository) refreshRepos();
    } finally {
      if (!controller.signal.aborted) {
        setCreating(false);
        setStage("idle");
      }
    }
  };

  const stageText: Record<CreateStage, string> = {
    idle: "",
    repository: "Adding repository…",
    bot: "Creating bot…",
    index: "Preparing project knowledge…"
  };

  return (
    <section className="bots-page">
      <header className="bots-heading">
        <div>
          <h1>Repository bots</h1>
          <p>One bot per repository. Each keeps its own instructions and conversation history.</p>
        </div>
        <button type="button" className="button button-secondary" disabled={loadingBots || creating} onClick={() => void refresh()} aria-label="Refresh bot list">
          <RefreshCw size={14} />Refresh list
        </button>
      </header>

      <div className="bots-layout">
        <section className="bots-library" aria-labelledby="bot-list-title">
          <div className="bots-section-title"><h2 id="bot-list-title">Bots by repository</h2><span>{bots.length}</span></div>
          {loadingBots ? <div className="bots-state">Loading bots…</div> : null}
          {loadError ? <div className="bots-message is-error" role="alert">{loadError}</div> : null}
          {!loadingBots && !loadError && bots.length === 0 ? (
            <div className="bots-empty"><strong>No bots yet</strong><p>Add a repository and create its first bot from the form.</p></div>
          ) : null}
          <div className="bot-repository-groups">
            {groupedBots.map(([repositoryName, group]) => (
              <section className="bot-repository-group" key={repositoryName}>
                <header><FolderGit2 size={15} /><strong>{repositoryName}</strong><span>{group.repo?.path ?? "Repository path unavailable"}</span></header>
                <div className="bot-row-list">
                  {group.bots.map((bot) => <BotRow key={bot.id} bot={bot} onOpen={() => onOpenBot(bot.id)} />)}
                </div>
              </section>
            ))}
          </div>
        </section>

        <section className="bot-create-panel" aria-labelledby="create-bot-title">
          <div className="bots-section-title"><h2 id="create-bot-title">Create a bot</h2></div>
          <p className="bot-form-intro">Select a repository or add a local folder or Git URL. The index is prepared before the conversation opens.</p>
          <form className="bot-create-form" onSubmit={(event) => void handleCreate(event)}>
            {!addRepository ? (
              <>
                <button
                  type="button"
                  className="bot-github-browse-button"
                  aria-expanded={githubPickerOpen}
                  aria-controls={githubPickerOpen ? "bot-github-repository-picker" : undefined}
                  onClick={() => setGithubPickerOpen((open) => !open)}
                >
                  <Github size={15} />{githubPickerOpen ? "Close GitHub browser" : "Browse GitHub repositories"}
                </button>
                {githubPickerOpen ? <div id="bot-github-repository-picker"><GitHubRepositoryPicker bots={bots} onSelect={selectGitHubRepository} /></div> : null}
                <label className="field"><span>Repository</span>
                  <select value={repoId} onChange={(event) => setRepoId(event.target.value)} disabled={reposLoading || availableRepos.length === 0}>
                    <option value="">{reposLoading ? "Loading repositories…" : "Choose a repository"}</option>
                    {availableRepos.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
                  </select>
                </label>
              </>
            ) : (
              <div className="bot-source-setup">
                <div className="bot-source-setup-title"><FolderGit2 size={15} /><strong>Add repository</strong></div>
                <label className="field"><span>Local folder or Git URL</span><input value={repoPath} onChange={(event) => setRepoPath(event.target.value)} placeholder="https://github.com/team/service.git" required /><small className="field-help">A local folder path refers to the Repo Brain server's disk, not your PC.</small></label>
                <label className="field"><span>Display name <small>Optional</small></span><input value={repoDisplayName} onChange={(event) => setRepoDisplayName(event.target.value)} placeholder="service" /></label>
              </div>
            )}
            <button type="button" className="bot-text-link" disabled={creating} onClick={() => { setAddRepository((value) => !value); setGithubPickerOpen(false); setCreateError(null); }}>
              {addRepository ? "Choose an existing repository" : "+ Add a repository"}
            </button>
            <label className="field"><span>Bot name</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Service guide" maxLength={120} required /></label>
            <label className="field"><span>Instructions <small>Optional</small></span><textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} placeholder="Give the bot a focus, such as API behavior or onboarding." rows={3} maxLength={4000} /></label>
            <label className="field"><span>OpenAI model ID</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="gpt-5.5" required /><small className="field-help">Use a model ID available to your OpenAI key, such as gpt-5.5. Custom IDs are sent as entered.</small></label>
            {reposError ? <div className="bots-message is-error" role="alert">{reposError}</div> : null}
            {createError ? <div className="bots-message is-error" role="alert">{createError}{createdBotId ? <button type="button" className="bot-text-link" onClick={() => onOpenBot(createdBotId)}>Open the created bot</button> : null}</div> : null}
            {createNotice ? <div className="bots-message" role="status"><RefreshCw size={14} className={creating ? "is-spinning" : undefined} />{stageText[stage] || createNotice}</div> : null}
            <button className="button button-primary" type="submit" disabled={loadingBots || creating || !name.trim() || !model.trim() || (addRepository ? !repoPath.trim() : !repoId)}>
              <Plus size={15} />{creating ? stageText[stage] || "Creating…" : "Create bot"}
            </button>
            <button type="button" className="bot-text-link bot-all-repos" onClick={onOpenRepos}>Manage repositories</button>
          </form>
        </section>
      </div>
    </section>
  );
}

function BotRow({ bot, onOpen }: { bot: Bot; onOpen: () => void }) {
  return (
    <button type="button" className="bot-row" onClick={onOpen}>
      <span className="bot-row-icon"><FileCode2 size={16} /></span>
      <span className="bot-row-main"><strong>{bot.name}</strong><span>{bot.instructions || "No extra instructions"}</span></span>
      <span className="bot-row-model">{bot.model}</span>
      <ChevronRight size={15} className="bot-row-chevron" />
    </button>
  );
}
