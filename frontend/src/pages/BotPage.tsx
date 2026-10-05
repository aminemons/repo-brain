import { ArrowLeft, Check, Clipboard, FileCode2, GitPullRequest, KeyRound, LoaderCircle, MessageSquareText, MessageSquarePlus, RefreshCw, Send, Settings2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  applyBotChange,
  checkBotDocumentation,
  createBotConversation,
  getBot,
  getBotChanges,
  getBotConversation,
  getBotConversations,
  getBotDocumentationStatus,
  publishBotChange,
  refreshBotKnowledge,
  proposeBotDocumentation,
  proposeBotChange,
  sendBotMessage,
  updateBot,
  type Bot,
  type BotChange,
  type BotConversation,
  type BotConversationDetail,
  type BotDocumentationStatus,
  type BotMessage,
  type BotRefreshResult
} from "../api/bots";
import { getRepos } from "../api/repos";

type BotMode = "explain" | "teach";
type BotTab = "chat" | "changes" | "documentation";

export function BotPage({ botId, onOpenLibrary }: { botId: string; onOpenLibrary: () => void }) {
  const [bot, setBot] = useState<Bot | null>(null);
  const [repoName, setRepoName] = useState("");
  const [conversations, setConversations] = useState<BotConversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BotConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [mode, setMode] = useState<BotMode>("explain");
  const [sending, setSending] = useState(false);
  const [refreshingKnowledge, setRefreshingKnowledge] = useState(false);
  const [refreshResult, setRefreshResult] = useState<BotRefreshResult | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [activeTab, setActiveTab] = useState<BotTab>("chat");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [botName, setBotName] = useState("");
  const [botInstructions, setBotInstructions] = useState("");
  const [botModel, setBotModel] = useState("");
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [autoDraft, setAutoDraft] = useState(false);
  const [autoDraftMessage, setAutoDraftMessage] = useState<string | null>(null);
  const autoDraftCommitRef = useRef<string | null>(null);
  const messageAbortRef = useRef<AbortController | null>(null);
  const refreshAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setApiKey("");
    setMessage("");
    setDetail(null);
    setConversationId(null);
    setBot(null);
    setError(null);
    setActiveTab("chat");
    setRefreshResult(null);
    setRefreshError(null);
    setRefreshingKnowledge(false);
    refreshAbortRef.current?.abort();
    refreshAbortRef.current = null;
    const controller = new AbortController();
    setLoading(true);
    setSending(false);
    messageAbortRef.current?.abort();
    messageAbortRef.current = null;
    Promise.all([getBot(botId, controller.signal), getBotConversations(botId, controller.signal), getRepos(controller.signal)])
      .then(([loadedBot, loadedConversations, repos]) => {
        if (controller.signal.aborted) return;
        setBot(loadedBot);
        setBotName(loadedBot.name);
        setBotInstructions(loadedBot.instructions);
        setBotModel(loadedBot.model);
        setConversations(loadedConversations);
        setRepoName(repos.find((repo) => repo.id === loadedBot.repo_id)?.name ?? "Repository");
        setConversationId(loadedConversations[0]?.id ?? null);
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) setError(loadError instanceof Error ? loadError.message : "Could not load bot.");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [botId]);

  useEffect(() => {
    if (!conversationId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setConversationLoading(true);
    getBotConversation(botId, conversationId, controller.signal)
      .then((loadedDetail) => { if (!controller.signal.aborted) setDetail(loadedDetail); })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) setError(loadError instanceof Error ? loadError.message : "Could not load conversation.");
      })
      .finally(() => { if (!controller.signal.aborted) setConversationLoading(false); });
    return () => controller.abort();
  }, [botId, conversationId]);

  useEffect(() => {
    if (!autoDraft || !apiKey.trim()) return;
    const controller = new AbortController();
    let checking = false;
    const poll = async () => {
      if (checking) return;
      checking = true;
      try {
        const current = await getBotDocumentationStatus(botId, controller.signal);
        if (controller.signal.aborted) return;
        const commit = current.current_commit;
        const pendingPaths = [...new Set(current.pending_jobs.filter((job) => job.status === "pending").map((job) => job.path))];
        const hasPending = pendingPaths.length > 0;
        if (commit && hasPending && commit !== autoDraftCommitRef.current && current.proposed_commit !== commit) {
          autoDraftCommitRef.current = commit;
          const paths = pendingPaths.slice(0, 20);
          await proposeBotDocumentation(botId, apiKey, paths, controller.signal);
          if (!controller.signal.aborted) {
            setError(null);
            setAutoDraftMessage(`Documentation draft prepared for ${commit.slice(0, 12)}. Review it under Code changes.`);
          }
        }
      } catch (pollError) {
        if (!controller.signal.aborted) {
          setAutoDraft(false);
          setError(pollError instanceof Error ? pollError.message : "Automatic documentation draft failed. Retry manually.");
        }
      } finally { checking = false; }
    };
    void poll();
    const intervalId = window.setInterval(() => void poll(), 60_000);
    return () => { controller.abort(); window.clearInterval(intervalId); };
  }, [apiKey, autoDraft, botId]);

  useEffect(() => () => { messageAbortRef.current?.abort(); }, []);
  useEffect(() => () => { refreshAbortRef.current?.abort(); }, []);

  const refreshKnowledge = async () => {
    if (refreshingKnowledge || sending) return;
    const controller = new AbortController();
    refreshAbortRef.current?.abort();
    refreshAbortRef.current = controller;
    setRefreshingKnowledge(true);
    setRefreshError(null);
    setRefreshResult(null);
    setError(null);
    try {
      const result = await refreshBotKnowledge(botId, controller.signal);
      if (!controller.signal.aborted) setRefreshResult(result);
    } catch (refreshFailure) {
      if (!controller.signal.aborted) setRefreshError(refreshFailure instanceof Error ? refreshFailure.message : "Could not refresh project knowledge.");
    } finally {
      if (!controller.signal.aborted) setRefreshingKnowledge(false);
    }
  };

  const startConversation = async () => {
    if (creatingConversation || refreshingKnowledge) return;
    setCreatingConversation(true);
    setError(null);
    try {
      const conversation = await createBotConversation(botId);
      messageAbortRef.current?.abort();
      setSending(false);
      setConversations((current) => [conversation, ...current]);
      setConversationId(conversation.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Could not start a conversation.");
    } finally {
      setCreatingConversation(false);
    }
  };

  const submitMessage = async (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || !conversationId || !apiKey.trim() || sending || refreshingKnowledge) return;
    setSending(true);
    setError(null);
    setMessage("");
    const controller = new AbortController();
    messageAbortRef.current?.abort();
    messageAbortRef.current = controller;
    try {
      const answer = await sendBotMessage(botId, conversationId, { message: text, mode, api_key: apiKey }, controller.signal);
      if (controller.signal.aborted) return;
      setDetail((current) => current ? { ...current, messages: [...current.messages, { id: `pending-${Date.now()}`, conversation_id: conversationId, role: "user", content: text, created_at: new Date().toISOString() }, answer] } : current);
      getBotConversation(botId, conversationId, controller.signal).then((loaded) => { if (!controller.signal.aborted) setDetail(loaded); }).catch(() => undefined);
      setConversations((current) => [...current].sort((a, b) => a.id === conversationId ? -1 : b.id === conversationId ? 1 : 0));
    } catch (sendError) {
      if (!controller.signal.aborted) {
        setMessage(text);
        const detail = sendError instanceof Error ? sendError.message : "Could not send message.";
        setError(/model request failed|invalid model|model.+not found|unsupported.+model/i.test(detail)
          ? `OpenAI could not complete a request with model “${bot?.model ?? "unknown"}”. Check that the model ID is valid and your key can access it.`
          : detail);
      }
    } finally {
      if (!controller.signal.aborted) setSending(false);
    }
  };

  const visibleError = error;
  const selectConversation = (id: string) => {
    messageAbortRef.current?.abort();
    setSending(false);
    setError(null);
    setConversationId(id);
  };

  const saveSettings = async (event: FormEvent) => {
    event.preventDefault();
    if (!bot || savingSettings || !botName.trim() || !botModel.trim()) return;
    setSavingSettings(true);
    setSettingsMessage(null);
    try {
      const updated = await updateBot(bot.id, { name: botName.trim(), model: botModel.trim(), instructions: botInstructions.trim() });
      setBot(updated);
      setSettingsMessage("Bot settings saved.");
    } catch (saveError) {
      setSettingsMessage(saveError instanceof Error ? saveError.message : "Could not save bot settings.");
    } finally { setSavingSettings(false); }
  };

  return (
    <section className="bot-workspace">
      <header className="bot-page-header">
        <div className="bot-page-title">
          <button type="button" className="bot-back-button" onClick={onOpenLibrary} aria-label="Back to bots"><ArrowLeft size={16} /></button>
          <span className="bot-avatar"><MessageSquareText size={18} /></span>
          <div><span className="bot-repo-context">{repoName || "Project repository"}</span><h1>{loading ? "Loading bot…" : bot?.name ?? "Bot"}</h1></div>
        </div>
        {bot ? <div className="bot-header-actions"><button type="button" className="bot-copy-link" onClick={() => void refreshKnowledge()} disabled={refreshingKnowledge || sending} title="Refresh the code and documentation index" aria-label={refreshingKnowledge ? "Refreshing knowledge" : "Refresh knowledge"}>{refreshingKnowledge ? <LoaderCircle size={14} className="bot-spinner" /> : <RefreshCw size={14} />}{refreshingKnowledge ? "Refreshing" : "Refresh knowledge"}</button><button type="button" className="bot-copy-link" onClick={() => { setSettingsOpen((open) => !open); setSettingsMessage(null); }}><Settings2 size={14} />Settings</button><CopyBotLink botId={bot.id} /></div> : null}
      </header>

      {visibleError ? <div className="bot-error" role="alert">{visibleError}</div> : null}
      {refreshError ? <div className="bot-error" role="alert">Knowledge refresh failed: {refreshError}</div> : null}
      {refreshingKnowledge ? <div className="bot-refresh-status" role="status"><LoaderCircle size={14} className="bot-spinner" />Refreshing project knowledge. Chat is paused until indexing finishes.</div> : null}
      {refreshResult ? <div className="bot-refresh-status is-complete" role="status"><Check size={14} /><span>Knowledge refreshed · {refreshResult.chunk_count} code chunks · {refreshResult.documents_indexed} documents indexed · {refreshResult.status} · commit {refreshResult.commit_hash?.slice(0, 12) ?? "unavailable"} · {formatDate(refreshResult.refreshed_at)}</span></div> : null}
      {refreshResult?.warnings?.length ? <div className="bot-refresh-warning" role="status">{refreshResult.warnings.join(" ")}</div> : null}
      {autoDraftMessage ? <div className="bot-notice" role="status">{autoDraftMessage}</div> : null}
      {loading ? <div className="bot-loading"><LoaderCircle size={17} className="bot-spinner" /> Loading bot…</div> : null}
      {!loading && bot ? (
        <div className="bot-main-layout">
          <aside className="bot-sidebar">
            <button type="button" className="bot-new-conversation" disabled={creatingConversation || refreshingKnowledge} onClick={() => void startConversation()}>
              <MessageSquarePlus size={15} />{creatingConversation ? "Starting…" : "New conversation"}
            </button>
            <div className="bot-conversation-label">Conversations</div>
            <div className="bot-conversation-list">
              {conversations.map((conversation) => (
                <button key={conversation.id} type="button" className={`bot-conversation-item${conversation.id === conversationId ? " is-active" : ""}`} onClick={() => selectConversation(conversation.id)}>
                  <span>{conversation.title || "New conversation"}</span><small>{formatDate(conversation.updated_at)}</small>
                </button>
              ))}
              {conversations.length === 0 ? <div className="bot-sidebar-empty">Your conversations will appear here.</div> : null}
            </div>
          </aside>
          <div className="bot-content">
            {settingsOpen ? <form className="bot-settings-form" onSubmit={(event) => void saveSettings(event)}>
              <div className="bot-settings-heading"><strong>Bot settings</strong><button type="button" className="bot-settings-close" onClick={() => setSettingsOpen(false)}>Close</button></div>
              <label className="field"><span>Name</span><input value={botName} onChange={(event) => setBotName(event.target.value)} required maxLength={120} /></label>
              <label className="field"><span>Instructions</span><textarea value={botInstructions} onChange={(event) => setBotInstructions(event.target.value)} rows={3} maxLength={4000} /></label>
              <label className="field"><span>OpenAI model ID</span><input value={botModel} onChange={(event) => setBotModel(event.target.value)} required /><small className="field-help">Use an ID available to your key, such as gpt-5.5. Custom IDs are sent as entered.</small></label>
              {settingsMessage ? <div className={settingsMessage === "Bot settings saved." ? "bot-notice" : "bot-error"} role="status">{settingsMessage}</div> : null}
              <button className="bots-primary-button" type="submit" disabled={!botName.trim() || !botModel.trim() || savingSettings}>{savingSettings ? "Saving…" : "Save settings"}</button>
            </form> : null}
            <nav className="bot-tabs" aria-label="Bot workspace">
              <button className={activeTab === "chat" ? "is-active" : undefined} onClick={() => setActiveTab("chat")}>Conversation</button>
              <button className={activeTab === "changes" ? "is-active" : undefined} onClick={() => setActiveTab("changes")}>Code changes</button>
              <button className={activeTab === "documentation" ? "is-active" : undefined} onClick={() => setActiveTab("documentation")}>Documentation</button>
            </nav>
            {activeTab === "chat" ? (
              <ChatPanel
                bot={bot}
                detail={detail}
                conversationLoading={conversationLoading}
                refreshingKnowledge={refreshingKnowledge}
                hasRefreshed={refreshResult !== null}
                apiKey={apiKey}
                onApiKeyChange={(value) => { setApiKey(value); if (!value.trim()) setAutoDraft(false); }}
                mode={mode}
                onModeChange={setMode}
                message={message}
                onMessageChange={setMessage}
                sending={sending}
                onSubmit={(event) => void submitMessage(event)}
              />
            ) : activeTab === "changes" ? (
              <ChangesPanel botId={botId} apiKey={apiKey} onApiKeyRequired={() => setActiveTab("chat")} />
            ) : <DocumentationPanel botId={botId} apiKey={apiKey} autoDraft={autoDraft} onAutoDraftChange={(value) => { setAutoDraft(value); autoDraftCommitRef.current = null; setAutoDraftMessage(null); setError(null); }} />}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ChatPanel({
  bot, detail, conversationLoading, refreshingKnowledge, hasRefreshed, apiKey, onApiKeyChange, mode, onModeChange, message, onMessageChange, sending, onSubmit
}: {
  bot: Bot;
  detail: BotConversationDetail | null;
  conversationLoading: boolean;
  refreshingKnowledge: boolean;
  hasRefreshed: boolean;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  mode: BotMode;
  onModeChange: (value: BotMode) => void;
  message: string;
  onMessageChange: (value: string) => void;
  sending: boolean;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <section className="bot-chat-panel">
      <div className="bot-chat-heading"><div><h2>{detail?.conversation.title || "Conversation"}</h2><span className="bot-model-context">{bot.model || "No model selected"}</span></div>
        <div className="bot-mode-switch" aria-label="Conversation mode">
          <button type="button" className={mode === "explain" ? "is-active" : undefined} onClick={() => onModeChange("explain")}>Explain</button>
          <button type="button" className={mode === "teach" ? "is-active" : undefined} onClick={() => onModeChange("teach")}>Teach</button>
        </div>
      </div>
      {bot.instructions ? <details className="bot-instructions"><summary>Bot instructions</summary><p>{bot.instructions}</p></details> : null}
      {!hasRefreshed && !detail?.messages.length ? <div className="bot-refresh-hint"><RefreshCw size={14} /><span>Refresh knowledge before your first conversation to index this repository's code and documentation.</span></div> : null}
      <div className="bot-messages" aria-live="polite">
        {conversationLoading ? <div className="bot-chat-empty">Loading conversation…</div> : null}
        {!conversationLoading && !detail ? <div className="bot-chat-empty"><MessageSquareText size={22} /><strong>Start a conversation</strong><span>Ask about this project, or switch to Teach to explore the code step by step.</span></div> : null}
        {detail?.messages.map((item) => <MessageBubble key={item.id} message={item} />)}
      </div>
      <form className={`bot-composer${refreshingKnowledge ? " is-disabled" : ""}`} onSubmit={onSubmit}>
        <label className="bot-key-field"><span><KeyRound size={13} /> OpenAI API key</span>
          <input type="password" autoComplete="off" spellCheck={false} value={apiKey} onChange={(event) => onApiKeyChange(event.target.value)} placeholder="sk-…" aria-label="Your OpenAI API key" />
        </label>
        <p className="bot-data-note">Your key stays in this page's memory and is sent with each AI request. Selected project excerpts are sent to OpenAI to answer.</p>
        <div className="bot-compose-row">
          <textarea value={message} onChange={(event) => onMessageChange(event.target.value)} placeholder={refreshingKnowledge ? "Chat will be available after refresh…" : mode === "teach" ? "What would you like to learn about?" : "Ask this bot about the project…"} rows={3} disabled={refreshingKnowledge} />
          <button type="submit" className="bots-primary-button bot-send-button" disabled={!apiKey.trim() || !message.trim() || !detail || sending || refreshingKnowledge} aria-label="Send message">
            {sending ? <LoaderCircle size={16} className="bot-spinner" /> : <Send size={16} />}{sending ? "Sending" : "Send"}
          </button>
        </div>
      </form>
    </section>
  );
}

function MessageBubble({ message }: { message: BotMessage }) {
  return (
    <article className={`bot-message${message.role === "user" ? " is-user" : " is-assistant"}`}>
      <div className="bot-message-role">{message.role === "user" ? "You" : "Bot"}</div>
      <div className="bot-message-content"><SafeMarkdown content={message.content} /></div>
      {message.sources?.length ? <div className="bot-citations"><strong>Project sources</strong>
        {message.sources.map((source) => <details key={source.id} className="bot-citation"><summary><strong className="bot-source-id">{source.id}</strong><FileCode2 size={13} /><span>{source.path}</span><small>:{source.start_line}–{source.end_line}</small></summary>{source.snippet ? <pre>{source.snippet}</pre> : null}</details>)}
      </div> : null}
    </article>
  );
}

function SafeMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a({ href, children }) {
          const external = href?.startsWith("https://") || href?.startsWith("http://");
          return <a href={href} target={external ? "_blank" : undefined} rel={external ? "noreferrer" : undefined}>{children}</a>;
        },
        img({ alt }) {
          return <span className="bot-remote-image-placeholder">{alt ? `Image omitted: ${alt}` : "Image omitted"}</span>;
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function CopyBotLink({ botId }: { botId: string }) {
  const [copied, setCopied] = useState(false);
  const url = `${window.location.origin}/bots/${encodeURIComponent(botId)}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch { setCopied(false); }
  };
  return <button type="button" className="bot-copy-link" onClick={() => void copy()} title={url}>{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? "Copied" : "Copy link"}</button>;
}

function ChangesPanel({ botId, apiKey, onApiKeyRequired }: { botId: string; apiKey: string; onApiKeyRequired: () => void }) {
  const [changes, setChanges] = useState<BotChange[]>([]);
  const [request, setRequest] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const refresh = useCallback((signal?: AbortSignal) => getBotChanges(botId, signal).then(setChanges), [botId]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    refresh(controller.signal).catch((loadError: unknown) => { if (!controller.signal.aborted) setError(loadError instanceof Error ? loadError.message : "Could not load code changes."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refresh]);

  const propose = async (event: FormEvent) => {
    event.preventDefault();
    if (!apiKey.trim()) { setError("Enter your OpenAI API key in the conversation tab to request a code change."); onApiKeyRequired(); return; }
    if (!request.trim() || working) return;
    setWorking("propose"); setError(null); setNotice(null);
    try { const proposal = await proposeBotChange(botId, request.trim(), apiKey); setChanges((current) => [proposal, ...current]); setRequest(""); }
    catch (proposalError) { setError(proposalError instanceof Error ? proposalError.message : "Could not propose a code change."); }
    finally { setWorking(null); }
  };

  const updateChange = async (change: BotChange, action: "apply" | "publish") => {
    setWorking(change.id); setError(null); setNotice(null);
    try {
      const updated = action === "apply" ? await applyBotChange(botId, change.id) : await publishBotChange(botId, change.id);
      setChanges((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(action === "apply" ? "Change applied on its branch." : "Pull request created.");
    } catch (actionError) { setError(actionError instanceof Error ? actionError.message : `Could not ${action} this change.`); }
    finally { setWorking(null); }
  };

  return <section className="bot-tool-panel">
    <div className="bot-tool-title"><div><span className="bot-tool-context">Review before applying</span><h2>Code changes</h2></div><span className="bot-review-badge">Manual review</span></div>
    <p>Describe a code change. Review the proposed diff, then apply it to a bot branch or create a pull request.</p>
    <form className="bot-change-form" onSubmit={(event) => void propose(event)}><label className="field"><span>What should change?</span><textarea rows={3} value={request} onChange={(event) => setRequest(event.target.value)} placeholder="Describe the change and the expected behavior…" /></label><button className="bots-primary-button" type="submit" disabled={!request.trim() || working !== null}><FileCode2 size={14} />{working === "propose" ? "Preparing proposal…" : "Propose change"}</button></form>
    {error ? <div className="bot-error" role="alert">{error}</div> : null}{notice ? <div className="bot-notice" role="status">{notice}</div> : null}
    {loading ? <div className="bots-state">Loading proposals…</div> : null}
    <div className="bot-change-list">{changes.map((change) => <ChangeCard key={change.id} change={change} working={working === change.id} onApply={() => void updateChange(change, "apply")} onPublish={() => void updateChange(change, "publish")} />)}</div>
    {!loading && changes.length === 0 ? <div className="bot-tool-empty">No code change proposals yet.</div> : null}
  </section>;
}

function ChangeCard({ change, working, onApply, onPublish }: { change: BotChange; working: boolean; onApply: () => void; onPublish: () => void }) {
  return <article className="bot-change-card">
    <div className="bot-change-header"><div><span className={`bot-change-status is-${change.status}`}>{change.status}</span><h3>{change.summary || change.request}</h3><small>{formatDate(change.created_at)}{change.branch ? ` · ${change.branch}` : ""}</small></div>
      {change.status === "proposed" ? <div className="bot-change-actions"><button type="button" onClick={onApply} disabled={working}>{working ? "Applying…" : "Apply on branch"}</button></div> : null}
      {change.status === "applied" ? <div className="bot-change-actions"><button type="button" onClick={onPublish} disabled={working}><GitPullRequest size={14} />{working ? "Creating…" : "Create PR"}</button></div> : null}
    </div>
    {change.error ? <div className="bot-error">{change.error}</div> : null}
    {change.files.length ? <div className="bot-change-files">{change.files.map((file) => <details key={file.path} className="bot-change-file"><summary><FileCode2 size={13} /><span>{file.path}</span><small>{file.action}</small></summary><pre>{file.diff || file.content || "No diff available."}</pre></details>)}</div> : null}
    {change.pull_request_url ? <a className="bot-pull-request-link" href={change.pull_request_url} target="_blank" rel="noreferrer"><GitPullRequest size={14} />Open pull request</a> : null}
    {change.base_commit ? <small className="bot-base-commit">Base commit {change.base_commit.slice(0, 12)}</small> : null}
  </article>;
}

function DocumentationPanel({ botId, apiKey, autoDraft, onAutoDraftChange }: { botId: string; apiKey: string; autoDraft: boolean; onAutoDraftChange: (value: boolean) => void }) {
  const [status, setStatus] = useState<BotDocumentationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const refresh = useCallback((signal?: AbortSignal) => getBotDocumentationStatus(botId, signal).then(setStatus), [botId]);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true);
    refresh(controller.signal).catch((loadError: unknown) => { if (!controller.signal.aborted) setError(loadError instanceof Error ? loadError.message : "Could not load documentation status."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refresh]);

  const check = async () => {
    setWorking(true); setError(null); setNotice(null);
    try { const result = await checkBotDocumentation(botId); setStatus(result); setNotice(`${result.queued_count ?? result.pending_jobs.length} documentation update${(result.queued_count ?? result.pending_jobs.length) === 1 ? "" : "s"} queued.`); }
    catch (checkError) { setError(checkError instanceof Error ? checkError.message : "Could not check documentation."); }
    finally { setWorking(false); }
  };

  const propose = async (event: FormEvent) => {
    event.preventDefault();
    if (!apiKey.trim()) { setError("Enter your OpenAI API key in the conversation tab to draft documentation."); return; }
    setWorking(true); setError(null); setNotice(null);
    try {
      const result = await proposeBotDocumentation(botId, apiKey, documentationPaths);
      setNotice(`Documentation proposal prepared (${result.status}). Review it under Code changes.`);
    } catch (proposalError) { setError(proposalError instanceof Error ? proposalError.message : "Could not propose documentation."); }
    finally { setWorking(false); }
  };

  const changedFiles = useMemo(() => status?.changed_files ?? [], [status]);
  const documentationPaths = useMemo(() => [...new Set(changedFiles)].slice(0, 20), [changedFiles]);
  const remainingFileCount = Math.max(0, new Set(changedFiles).size - documentationPaths.length);
  return <section className="bot-tool-panel">
    <div className="bot-tool-title"><div><span className="bot-tool-context">Project knowledge</span><h2>Documentation</h2></div><button className="bot-secondary-button" type="button" onClick={() => void check()} disabled={working}>{working ? "Checking…" : "Check for changes"}</button></div>
    <p>Check the repository for changes since its documentation was last recorded, or ask the bot to draft an update.</p>
    <label className="bot-auto-draft"><input type="checkbox" checked={autoDraft} disabled={!apiKey.trim()} onChange={(event) => onAutoDraftChange(event.target.checked)} /><span><strong>Automatically draft documentation while this page is open</strong><small>Needs your OpenAI key in the Conversation tab. Checks every 60 seconds and prepares a reviewable draft only.</small></span></label>
    {loading ? <div className="bots-state">Loading documentation status…</div> : null}
    <div className="bot-doc-summary"><div><span>Recorded commit</span><strong>{status?.recorded_commit?.slice(0, 12) ?? "Not recorded"}</strong></div><div><span>Current commit</span><strong>{status?.current_commit?.slice(0, 12) ?? "Unavailable"}</strong></div><div><span>Last checked</span><strong>{status?.last_checked_at ? formatDate(status.last_checked_at) : "Never"}</strong></div></div>
    <div className="bot-doc-files"><strong>Changed files ({changedFiles.length})</strong>{changedFiles.length ? changedFiles.map((path) => <span key={path}><FileCode2 size={13} />{path}</span>) : <small>No changed files reported.</small>}</div>
    {status?.pending_jobs.length ? <div className="bot-doc-files"><strong>Pending updates</strong>{status.pending_jobs.map((job) => <span key={`${job.path}-${job.detected_at}`}><LoaderCircle size={13} />{job.path} · {job.status}</span>)}</div> : null}
    <form className="bot-change-form" onSubmit={(event) => void propose(event)}><div className="bot-doc-selection"><strong>Draft next up to 20 changed files</strong><small>The bot uses changed repository files as context for a reviewable proposal.{remainingFileCount > 0 ? ` ${remainingFileCount} files remain for a later batch.` : ""}</small></div><button className="bots-primary-button" type="submit" disabled={working}><FileCode2 size={14} />Draft documentation</button></form>
    {error ? <div className="bot-error" role="alert">{error}</div> : null}{notice ? <div className="bot-notice" role="status">{notice}</div> : null}
  </section>;
}

function formatDate(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}
