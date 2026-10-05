export const TOKEN_STORAGE_KEY = "project-brain.token";
export const TOKEN_CHANGED_EVENT = "project-brain:token-changed";
export const AUTH_REQUIRED_EVENT = "project-brain:auth-required";

export function readAccessToken(): string {
  return window.sessionStorage.getItem(TOKEN_STORAGE_KEY) ?? "";
}

export function saveAccessToken(token: string): void {
  const value = token.trim();
  if (value) {
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, value);
  } else {
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
  window.dispatchEvent(new Event(TOKEN_CHANGED_EVENT));
}
