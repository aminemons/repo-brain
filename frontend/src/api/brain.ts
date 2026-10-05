import { API_BASE, apiFetch, readJson } from "./http";
import type {
  ArtifactListResponse, BrainAnswer, BrainStatus, DocumentSearchResponse,
  DocumentSection, DocumentVersion, IngestDocumentResponse, SourceExcerpt
} from "../brain/types";

function brainPath(repoId: string): string {
  return `${API_BASE}/repos/${encodeURIComponent(repoId)}/brain`;
}

async function readBrain<T>(url: string, label: string, signal?: AbortSignal): Promise<T> {
  return readJson<T>(await apiFetch(url, { signal }), label);
}

export function getBrainStatus(repoId: string, signal?: AbortSignal): Promise<BrainStatus> {
  return readBrain(brainPath(repoId), "Project knowledge", signal);
}

export function searchBrainDocuments(repoId: string, query = "", signal?: AbortSignal): Promise<DocumentSearchResponse> {
  const search = new URLSearchParams({ query, limit: "40" });
  return readBrain(`${brainPath(repoId)}/documents?${search}`, "Documentation search", signal);
}

export function getBrainDocumentSection(repoId: string, sectionId: string, signal?: AbortSignal): Promise<DocumentSection> {
  return readBrain(`${brainPath(repoId)}/documents/${encodeURIComponent(sectionId)}`, "Document section", signal);
}

export function getBrainDocumentVersions(repoId: string, documentId: string, signal?: AbortSignal): Promise<DocumentVersion[]> {
  return readBrain(`${brainPath(repoId)}/documents/${encodeURIComponent(documentId)}/versions`, "Document versions", signal);
}

export async function ingestBrainDocument(repoId: string, payload: { path: string; title?: string; authoritative: boolean }): Promise<IngestDocumentResponse> {
  const response = await apiFetch(`${brainPath(repoId)}/documents`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
  });
  return readJson(response, "Document ingestion");
}

export function getBrainWalkthrough(repoId: string, query = "", signal?: AbortSignal): Promise<BrainAnswer> {
  const search = new URLSearchParams({ query, limit: "12" });
  return readBrain(`${brainPath(repoId)}/walkthrough?${search}`, "Learning map", signal);
}

export function getBrainArtifacts(repoId: string, query = "", signal?: AbortSignal): Promise<ArtifactListResponse> {
  const search = new URLSearchParams({ query, limit: "30" });
  return readBrain(`${brainPath(repoId)}/artifacts?${search}`, "Artifacts", signal);
}

export function getBrainArtifactVersions(repoId: string, artifactId: string, signal?: AbortSignal): Promise<ArtifactListResponse> {
  return readBrain(`${brainPath(repoId)}/artifacts/${encodeURIComponent(artifactId)}/versions`, "Artifact versions", signal);
}

export function getBrainSource(repoId: string, path: string, startLine: number, endLine: number, signal?: AbortSignal, kind: "code" | "documentation" = "code"): Promise<SourceExcerpt> {
  const search = new URLSearchParams({ path, start_line: String(startLine), end_line: String(endLine), kind });
  return readBrain(`${brainPath(repoId)}/source?${search}`, "Source excerpt", signal);
}
