import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { askRepo } from "../../api/ask";
import type { AskResponse } from "../../api/types";
import { getRelatedNodeIds, highlightRelatedNodes } from "../graphHighlight";

export function useAsk(selectedRepoId: string) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setAnswer(null);
    setError(null);
    setLoading(false);
    return () => requestRef.current?.abort();
  }, [selectedRepoId]);

  const relatedNodeIds = useMemo(() => getRelatedNodeIds(answer), [answer]);

  const submitQuestion = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      const trimmedQuestion = question.trim();
      if (!selectedRepoId || !trimmedQuestion || loading) {
        return;
      }

      setLoading(true);
      setError(null);
      const controller = new AbortController();
      requestRef.current = controller;
      try {
        const response = await askRepo(selectedRepoId, trimmedQuestion, controller.signal);
        if (controller.signal.aborted) return;
        setAnswer(response);
        highlightRelatedNodes(selectedRepoId, response);
      } catch (apiError) {
        if (controller.signal.aborted) return;
        setAnswer(null);
        setError(apiError instanceof Error ? apiError.message : "Ask failed");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    },
    [loading, question, selectedRepoId]
  );

  const highlightCurrentAnswer = useCallback(() => {
    if (answer && selectedRepoId) {
      highlightRelatedNodes(selectedRepoId, answer);
    }
  }, [answer, selectedRepoId]);

  return {
    question,
    setQuestion,
    answer,
    loading,
    error,
    relatedNodeIds,
    submitQuestion,
    highlightCurrentAnswer
  };
}
