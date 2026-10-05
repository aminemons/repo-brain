import { API_BASE, apiFetch, readJson } from "./http";
import type { LlmModelsResponse } from "./types";

export async function getLlmModels(): Promise<LlmModelsResponse> {
  const response = await apiFetch(`${API_BASE}/settings/llm/models`);
  return readJson(response, "LLM settings");
}
