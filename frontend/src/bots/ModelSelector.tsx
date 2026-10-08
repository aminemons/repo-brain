const LOCAL_MODEL = "ollama/qwen2.5-coder:0.5b";

export function isLocalModel(model: string | undefined): boolean {
  return model?.trim().toLowerCase().startsWith("ollama/") ?? false;
}

export function ModelSelector({ model, onChange }: { model: string; onChange: (model: string) => void }) {
  const local = isLocalModel(model);
  return <>
    <label className="field"><span>Model provider</span>
      <select value={local ? "local" : "openai"} onChange={(event) => onChange(event.target.value === "local" ? LOCAL_MODEL : (local ? "gpt-5.5" : model))}>
        <option value="local">Local (free)</option>
        <option value="openai">OpenAI (your key)</option>
      </select>
    </label>
    <label className="field"><span>{local ? "Ollama model ID" : "OpenAI model ID"}</span>
      <input value={model} onChange={(event) => onChange(event.target.value)} required />
      <small className="field-help">{local ? "Uses the Ollama model available to the Repo Brain server." : "Use a model ID available to your OpenAI key. Custom IDs are sent as entered."}</small>
    </label>
  </>;
}
