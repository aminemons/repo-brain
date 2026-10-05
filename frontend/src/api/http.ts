import { AUTH_REQUIRED_EVENT, readAccessToken } from "./auth";

export const API_BASE = "/api";
export const API_UNREACHABLE_EVENT = "project-brain:api-unreachable";

export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = readAccessToken();
  const destination = new URL(url, window.location.origin);
  if (destination.origin !== window.location.origin || !destination.pathname.startsWith(`${API_BASE}/`)) {
    throw new Error("API requests must use this application's API.");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let response: Response;
  try {
    response = await fetch(url, { ...init, headers });
  } catch (error) {
    if (!init.signal?.aborted) {
      window.dispatchEvent(new Event(API_UNREACHABLE_EVENT));
      throw new Error("Repo Brain could not reach its local service. Check that the app server is running, then retry.");
    }
    throw error;
  }
  if (response.status === 401 && token === readAccessToken()) {
    window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
  }
  return response;
}

export async function readJson<T>(response: Response, label: string): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("The API access token is missing or was rejected. Open Settings to enter your token.");
    }
    const detail = await readErrorDetail(response, contentType);
    throw new Error(`${label} failed: ${response.status}${detail ? ` - ${detail}` : ""}`);
  }
  if (!isJsonResponse(contentType)) {
    const preview = await readTextPreview(response);
    throw new Error(
      `${label} failed: expected JSON from the API but received ${describeContentType(contentType)}.` +
        `${preview ? ` Response started with: ${preview}` : ""}`
    );
  }
  return response.json() as Promise<T>;
}

async function readErrorDetail(response: Response, contentType: string): Promise<string> {
  if (!isJsonResponse(contentType)) {
    return readTextPreview(response);
  }
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : "";
  } catch {
    return "";
  }
}

async function readTextPreview(response: Response): Promise<string> {
  try {
    return (await response.text()).trim().replace(/\s+/g, " ").slice(0, 120);
  } catch {
    return "";
  }
}

function isJsonResponse(contentType: string): boolean {
  return contentType.toLowerCase().includes("application/json");
}

function describeContentType(contentType: string): string {
  return contentType ? contentType.split(";")[0] : "non-JSON content";
}
