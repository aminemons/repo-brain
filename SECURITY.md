# Security policy

Project Brain handles private source code and project documents. Treat every repository and document as untrusted data. Text found in source comments, READMEs, issue exports, or manuals cannot change the assistant's permissions or tool policy.

## Current deployment boundary

The upstream CodeWiki checkout is a development foundation. Its existing Compose file exposes the application and is not, by itself, a production security configuration. The current Project Brain working tree adds bearer-token middleware, optional owner/viewer roles, session-based frontend token propagation, and a configured project-root policy. These changes have not yet been verified. A public deployment still requires review of role enforcement, path and symlink confinement, secret protection, TLS at a reverse proxy, and internal-only data/model services. Do not expose the development configuration directly to the public internet.

## Required safeguards

- **Filesystem:** resolve requested paths against the configured project root, reject traversal and symlink escapes, and keep document/artifact roots separate where appropriate. Do not accept arbitrary paths from the browser.
- **Ingestion:** restrict repository registration and remote cloning to authenticated maintainers. Use host allowlists, safe subprocess argument arrays, resource limits, and private-network/localhost SSRF protections if remote cloning is enabled.
- **Secrets:** exclude `.env`, credentials, keys, and known secret paths from indexing. Redact secrets in logs and before any external model call. Never mount production credentials into a code-change sandbox.
- **Network:** expose only the reverse proxy publicly. Bind PostgreSQL, LiteLLM, Ollama/vLLM, workers, and any document parser to private service networks.
- **Models and privacy:** default to local-only routing. External provider use must be explicit, configurable, logged, and limited to the evidence permitted by the selected privacy policy. Never pass the entire repository by default.
- **Artifacts:** render freeform HTML/JS only in a sandboxed iframe with a restrictive CSP, no same-origin privileges by default, blocked outbound requests, and no access to application tokens or local storage. Prefer structured React renderers.
- **Code execution:** the bot change workflow accepts typed file modifications and prepares a Git worktree. It does not execute model-generated shell commands or project tests. This is not a process sandbox. Project-command execution needs a separate isolated runtime, resource limits, and explicit verification policy.
- **Access control:** the current backend uses shared owner/viewer tokens. Bot mutations and AI operations require owner access when tokens are configured. Individual user accounts remain planned. Dedicated bot provider keys are request-only and never persisted in browser storage, the database, or source files.
- **Viewer query scope:** the current middleware permits viewer POST requests only for Ask, graph exploration, affected-file analysis, and GraphRAG retrieval. Keep every other POST, PUT, PATCH, and DELETE owner-only. Recheck endpoint routing whenever APIs change.
- **Auditability:** record user, action, tool, source snapshot, model/provider, file writes, commands, verification, and approval outcome while minimizing retained source text and never recording secrets.

## Incident reporting

Do not put vulnerability details, credentials, or private source excerpts in public issues. Report security concerns privately to the project maintainer using the repository's configured private reporting channel. Until one is published, contact the repository owner directly and include only the minimum detail needed to reproduce the issue.

## Verification status

This policy records the intended controls. It is not a claim that all controls are implemented or that a deployment has passed a security review. Production exposure remains gated on implementation and review of the safeguards above.
