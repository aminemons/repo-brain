import { useEffect, useState } from "react";

import { AskForm } from "../ask/components/AskForm";
import { AskResult } from "../ask/components/AskResult";
import { useAsk } from "../ask/hooks/useAsk";
import { getLlmModels } from "../api/settings";
import { useRepos } from "../hooks/useRepos";

export function AskPage({
  selectedRepoId,
  onRepoChange,
  onOpenBots,
  isActiveSection
}: {
  selectedRepoId: string;
  onRepoChange: (repoId: string) => void;
  onOpenBots: (repoId: string) => void;
  isActiveSection: boolean;
}) {
  const [qaModelConfigured, setQaModelConfigured] = useState<boolean | null>(null);
  const { repos, selectedRepo, error: repoError } = useRepos({ selectedRepoId, onRepoChange });
  const {
    question,
    setQuestion,
    answer,
    loading,
    error: askError,
    relatedNodeIds,
    submitQuestion,
    highlightCurrentAnswer
  } = useAsk(selectedRepoId);

  useEffect(() => {
    let current = true;
    void getLlmModels().then((settings) => {
      if (!current) return;
      const qaProfile = settings.profiles.qa;
      setQaModelConfigured(qaProfile.model !== "provider/strong-coding-model");
    }).catch(() => {
      if (current) setQaModelConfigured(true);
    });
    return () => { current = false; };
  }, []);

  return (
    <section id="ask" className={`side-panel ask-panel${isActiveSection ? " is-nav-target" : ""}`}>
      <header>
        <span className="eyebrow">Ask</span>
        <h2>{qaModelConfigured === false ? "Ask with a repository bot" : "Legacy GraphRAG"}</h2>
        {qaModelConfigured === false ? (
          <p className="ask-mode-help">Use your repository bot to ask with your OpenAI key. The server Ask model has not been configured.</p>
        ) : (
          <p className="ask-mode-help">Uses the server-configured model. For an OpenAI key you provide, use a repository bot.</p>
        )}
        <button type="button" className="ask-bot-link" disabled={!selectedRepoId} onClick={() => onOpenBots(selectedRepoId)}>
          Open or create a bot for this repository
        </button>
      </header>

      {qaModelConfigured === false ? null : (
        <AskForm
          repos={repos}
          selectedRepoId={selectedRepoId}
          question={question}
          loading={loading}
          onRepoChange={onRepoChange}
          onQuestionChange={setQuestion}
          onSubmit={submitQuestion}
        />
      )}

      {selectedRepo ? <div className="ask-repo-path">{selectedRepo.path}</div> : null}
      {repoError || askError ? <div className="ask-error">{repoError ?? askError}</div> : null}

      {answer ? (
        <AskResult key={answer.trace_id} repoId={selectedRepoId} answer={answer} relatedNodeIds={relatedNodeIds} onHighlight={highlightCurrentAnswer} />
      ) : null}
    </section>
  );
}
