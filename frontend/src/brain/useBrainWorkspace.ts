import { useEffect, useState } from "react";

import { getBrainArtifacts, getBrainStatus, getBrainWalkthrough, searchBrainDocuments } from "../api/brain";
import type { BrainAnswer, BrainArtifact, BrainStatus, DocumentSection } from "./types";

export type BrainView = "learn" | "documents" | "artifacts";

export function useBrainWorkspace(repoId: string, view: BrainView, query: string) {
  const [status, setStatus] = useState<BrainStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentSection[]>([]);
  const [answer, setAnswer] = useState<BrainAnswer | null>(null);
  const [artifacts, setArtifacts] = useState<BrainArtifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setStatusError(null);
    getBrainStatus(repoId, controller.signal).then(setStatus).catch((reason: unknown) => {
      if (!controller.signal.aborted) setStatusError(errorMessage(reason));
    });
    return () => controller.abort();
  }, [repoId, revision]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const request = view === "documents"
      ? searchBrainDocuments(repoId, query, controller.signal).then((data) => setDocuments(data.results))
      : view === "artifacts"
        ? getBrainArtifacts(repoId, query, controller.signal).then((data) => setArtifacts(data.artifacts))
        : getBrainWalkthrough(repoId, query, controller.signal).then(setAnswer);
    request.catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [repoId, view, query, revision]);

  return { status, statusError, documents, answer, artifacts, loading, error,
    refresh: () => setRevision((value) => value + 1) };
}

export function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "The API request failed. Check the connection and try again.";
}
