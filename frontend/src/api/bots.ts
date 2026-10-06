import { API_BASE, apiFetch, readJson } from "./http";

export type Bot = {
  id: string;
  repo_id: string;
  name: string;
  instructions: string;
  model: string;
  created_at: string;
  updated_at: string;
};

export type BotConversation = {
  id: string;
  bot_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type BotSource = {
  id: string;
  type: "code" | "documentation";
  path: string;
  start_line: number;
  end_line: number;
  snippet: string;
};

export type BotMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  sources?: BotSource[];
  illustration?: BotIllustration | null;
};

export type BotIllustration = {
  status: "ready" | "unavailable";
  url?: string;
  caption: string;
  alt_text?: string;
  detail?: string;
};

export type BotConversationDetail = {
  conversation: BotConversation;
  messages: BotMessage[];
};

export type BotRefreshResult = {
  repo_id: string;
  status: string;
  chunk_count: number;
  documents_indexed: number;
  commit_hash: string | null;
  refreshed_at: string;
  warnings?: string[];
};

const botsUrl = `${API_BASE}/bots`;

export async function getBots(repoId?: string, signal?: AbortSignal): Promise<{ bots: Bot[] }> {
  const query = repoId ? `?repo_id=${encodeURIComponent(repoId)}` : "";
  const response = await apiFetch(`${botsUrl}${query}`, { signal });
  return readJson(response, "Bot list");
}

export async function createBot(
  payload: { repo_id: string; name: string; instructions?: string; model?: string },
  signal?: AbortSignal
): Promise<Bot> {
  const response = await apiFetch(botsUrl, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readJson(response, "Bot create");
}

export async function getBot(botId: string, signal?: AbortSignal): Promise<Bot> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}`, { signal });
  return readJson(response, "Bot details");
}

export async function updateBot(
  botId: string,
  payload: { name?: string; instructions?: string; model?: string },
  signal?: AbortSignal
): Promise<Bot> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}`, {
    method: "PATCH",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readJson(response, "Bot update");
}

export async function refreshBotKnowledge(botId: string, signal?: AbortSignal): Promise<BotRefreshResult> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/refresh`, { method: "POST", signal });
  return readJson(response, "Knowledge refresh");
}

export async function getBotConversations(botId: string, signal?: AbortSignal): Promise<BotConversation[]> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/conversations`, { signal });
  return readJson(response, "Conversation list");
}

export async function createBotConversation(botId: string, title?: string): Promise<BotConversation> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(title ? { title } : {})
  });
  return readJson(response, "Conversation create");
}

export async function getBotConversation(
  botId: string,
  conversationId: string,
  signal?: AbortSignal
): Promise<BotConversationDetail> {
  const response = await apiFetch(
    `${botsUrl}/${encodeURIComponent(botId)}/conversations/${encodeURIComponent(conversationId)}`,
    { signal }
  );
  return readJson(response, "Conversation");
}

export async function sendBotMessage(
  botId: string,
  conversationId: string,
  payload: { message: string; mode: "explain" | "teach" | "illustrate"; api_key: string },
  signal?: AbortSignal
): Promise<BotMessage> {
  const response = await apiFetch(
    `${botsUrl}/${encodeURIComponent(botId)}/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
  return readJson(response, "Bot message");
}

export async function getBotIllustration(botId: string, messageId: string, signal?: AbortSignal): Promise<Blob> {
  const response = await apiFetch(
    `${botsUrl}/${encodeURIComponent(botId)}/messages/${encodeURIComponent(messageId)}/illustration`,
    { signal }
  );
  if (!response.ok) {
    throw new Error(response.status === 404
      ? "The Najm illustration is no longer available."
      : `Could not load the Najm illustration (${response.status}).`);
  }
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("image/png")) {
    throw new Error("The illustration service returned an unexpected file type.");
  }
  return response.blob();
}

export type BotChange = {
  id: string;
  bot_id: string;
  status: "proposed" | "applied" | "published" | "failed";
  request: string;
  branch?: string | null;
  base_commit?: string | null;
  summary?: string | null;
  files: Array<{ path: string; action: string; content?: string; diff?: string }>;
  created_at: string;
  updated_at: string;
  error?: string | null;
  pull_request_url?: string | null;
};

export type BotDocumentationStatus = {
  bot_id: string;
  recorded_commit?: string | null;
  current_commit?: string | null;
  changed_files: string[];
  pending_jobs: Array<{ path: string; status: string; detected_at: string }>;
  last_checked_at?: string | null;
  proposed_commit?: string | null;
};

export async function getBotChanges(botId: string, signal?: AbortSignal): Promise<BotChange[]> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/changes`, { signal });
  return readJson(response, "Change list");
}

export async function proposeBotChange(
  botId: string,
  request: string,
  apiKey: string,
  signal?: AbortSignal
): Promise<BotChange> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/changes`, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request, api_key: apiKey })
  });
  return readJson(response, "Change proposal");
}

export async function applyBotChange(botId: string, changeId: string): Promise<BotChange> {
  const response = await apiFetch(
    `${botsUrl}/${encodeURIComponent(botId)}/changes/${encodeURIComponent(changeId)}/apply`,
    { method: "POST" }
  );
  return readJson(response, "Change apply");
}

export async function publishBotChange(botId: string, changeId: string): Promise<BotChange> {
  const response = await apiFetch(
    `${botsUrl}/${encodeURIComponent(botId)}/changes/${encodeURIComponent(changeId)}/publish`,
    { method: "POST" }
  );
  return readJson(response, "Change publish");
}

export async function getBotDocumentationStatus(
  botId: string,
  signal?: AbortSignal
): Promise<BotDocumentationStatus> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/documentation/status`, { signal });
  return readJson(response, "Documentation status");
}

export async function checkBotDocumentation(botId: string): Promise<BotDocumentationStatus & { queued_count?: number }> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/documentation/check`, { method: "POST" });
  return readJson(response, "Documentation check");
}

export async function proposeBotDocumentation(botId: string, apiKey: string, paths?: string[], signal?: AbortSignal): Promise<BotChange> {
  const response = await apiFetch(`${botsUrl}/${encodeURIComponent(botId)}/documentation/propose`, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, ...(paths?.length ? { paths } : {}) })
  });
  return readJson(response, "Documentation proposal");
}
