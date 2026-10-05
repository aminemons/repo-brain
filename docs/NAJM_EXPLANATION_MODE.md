# Najm explanation mode

Status: proposal. No renderer, mode toggle, or execution sandbox has been implemented.

## Developer experience

Add **Illustrate** as an optional choice for a bot question, alongside Explain and Teach. Keep the same repository bot, instructions, conversation, and source evidence. Return the normal cited answer with an additional illustration when rendering succeeds.

Start with a call-chain diagram exported to PNG. A short video can highlight steps whose ordering is supported by repository evidence. Keep captions and source links beside the media. Distinguish a possible static path from an observed runtime trace. Each bot's media and manifests must remain scoped to that bot's repository.

## Why Najm

[Najm](https://github.com/XMinty77/Najm) provides a C# scene model and rendering primitives for educational visuals. We reviewed commit `6e898a51c7e7e2f0992a194891491fd1253c246e`, including its PNG exporter, Orrery delivery driver, architecture, roadmap, and MIT license.

The current source supports a practical first step through exported images and video. Najm is under active development with an unstable public API. Its documented native setup currently targets Linux with .NET 10.0.111 or a later supported patch. Direct browser hosting and vector export must be checked against implementation status before becoming requirements.

## Proposed application boundary

Repo Brain retrieves and checks evidence, builds a bounded explanation plan, and owns bot access, model requests, provenance, and cache invalidation. A separate adapter maps validated plan data to reviewed Najm C# templates. Najm renders the scene; it does not manage repository indexing or model access.

Record the repository commit, Najm revision, template version, render settings, and evidence IDs in each artifact manifest. Mark media stale when the repository changes. Generate or regenerate only when the developer asks to illustrate a question.

Rendering must run in an isolated worker with filesystem, network, resource, and output limits. Do not execute arbitrary model-generated C# or run code from the indexed repository. The worker needs selected labels and relationships, not API keys, GitHub credentials, full checkouts, or complete conversation history. Keep the cited answer available if rendering fails.

## First implementation gates

1. Choose a pinned Najm revision and preserve MIT and bundled third-party notices when distributing components.
2. Build one reviewed call-chain template and validate a bounded input schema.
3. Provide the rendering sandbox before enabling the mode.
4. Render a small public fixture and verify source links, captions, readability, timing, and repeatability in the pinned environment.
5. Add the UI toggle and media response only after those gates pass.

Fine-tuning is not a prerequisite for this proposal. The model would explain retrieved evidence and produce validated scene data; the template would control the drawing.

## Small upstream contribution

A documentation-only proposal was submitted as [Najm PR #1](https://github.com/XMinty77/Najm/pull/1). It describes the relationship with Repo Brain and the adapter boundary. The PR is a draft for maintainer review; its existence does not imply acceptance or an implemented integration.
