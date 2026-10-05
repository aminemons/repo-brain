# Build report

## Chat and Git fixes — 2026-10-05

Follow-up: the WMI-launched server also disappeared after the chat turn ended. Background startup now uses Windows Task Scheduler with an interactive, non-elevated principal and no triggers. The API health check and browser bot library loaded successfully after that change. The earlier cross-command check did not establish survival beyond the chat turn.

The local API had stopped. A bot package export also prevented startup after the latest edits. The chat API now indexes a fresh repository before retrieval and returns useful provider errors without exposing request credentials. The background PowerShell launcher was exercised successfully against the local API.

Integration tests found an empty worktree index during change application. Seeding it with the base commit now preserves untouched tracked files. The regression tests cover that behavior, optimistic checks, documentation completion after merge, deduplication and batching, commit detection, and a stubbed publication path.

Verification so far:

- Chat API integration test passed with a temporary repository and stub OpenAI provider. It covers registration, bot uniqueness, first-chat indexing, persistence, `store=False`, refresh, model error handling, and absence of the key from SQLite/WAL.
- Six Git workflow integration tests passed using temporary repositories; publishing is stubbed.
- The combined chat and Git regression suite passed: seven tests in 48.84 seconds. FastAPI's inherited TestClient emits an httpx deprecation warning.
- Full backend mypy passed for 259 source files. Focused bot Ruff checks passed.
- The detached local server returned `{"status":"ok"}` from `/api/health` and binds to `127.0.0.1:8000`.
- The final frontend build and focused ESLint passed. Browser review covered the bot library, conversation/settings navigation, saved model changes, connection failure reporting, and the mobile composer at 390 × 844 with no horizontal page overflow.
- The Windows launcher uses a hidden WMI worker to detach the server from the launching tool session. The root-launched instance remained healthy across later build, Git, browser, and packaging commands.
- The first GitHub workflow run passed. It checks the bot backend, all backend types, the focused regression suite, and frontend compilation.

The inherited full Ruff check reports existing violations across the base application and tests. GitHub's default workflow explicitly checks the bot modules and focused regression tests, all backend types, and the frontend build. The inherited full test suite remains an optional manual run. No paid model request, real target-repository push/PR, OVH deployment, or sandboxed project command execution was performed.

## Dedicated bot release — 2026-10-04

The repository bot implementation was finished with GPT-6 Luna agents. It adds a bot library and stable bot links, separate persisted conversations, editable per-bot settings, request-only OpenAI key handling, Explain/Teach modes, knowledge refresh, reviewed file proposals, isolated Git branches and pull-request publication. Documentation tracking detects commit changes, refreshes knowledge, and supports reviewable drafts in batches of up to 20 changed source paths. Optional automatic drafting runs only while the bot page is open with its key entered.

Final checks for this update:

- Frontend TypeScript/Vite build and focused ESLint passed after the refresh and batching UI changes.
- Full backend mypy passed: 259 source files.
- Ruff passed for the new bot APIs, schemas, services and changed application/config/security modules.
- Python compilation, dependency lock consistency (135 packages) and Git whitespace checks passed.
- The local application started successfully on `http://127.0.0.1:8000`; Uvicorn logged application startup complete and listening. The earlier server instance was replaced.

The build retains the existing JavaScript chunk-size warning. No automated tests, browser interaction tests, model requests, target-repository analysis, real change branches, or GitHub pull requests were run for this update. Startup confirms that the application launches; it does not verify the full bot or Git workflow.

Initial access uses the application's shared owner token. Individual user accounts, a process sandbox for running project commands, target evaluations, and OVH deployment remain unfinished. Proposals use bounded whole-file text edits and refuse unsupported/sensitive inputs. Tests remain deferred by the owner's direction. The source ZIP includes the compiled interface and excludes local data, environments and credentials.

## Initial implementation — 2026-10-03

Date: 2026-10-03. This report describes compilation and static checks of the first Project Brain implementation. The user deferred tests and target-repository evaluation.

| Check | Result | Scope |
|---|---|---|
| Frontend TypeScript and Vite build | Passed | Final frontend, including Brain workspace, Ask citations and session authorization. Assets are included under `backend/app/static`. |
| Frontend ESLint | Passed | Changed frontend modules, as checked by the GPT-6.1 Sol frontend agent. |
| Python compilation | Passed | `backend/app`; checked using local Python 3.13.3. Production Docker uses Python 3.12. |
| Python mypy | Passed | All 248 backend source files. Three inherited standard-input typing errors were repaired using `sys.stdin`. |
| Python Ruff | Passed | Changed Python modules and the new Project Brain API, schemas and services. |
| Dependency lock consistency | Passed | `uv lock --check --offline`; lock resolves 135 packages, including the optional PDF extra. |
| Compose configuration | Passed | Static `docker compose ... config --quiet` using the example deployment values. No services were launched. |
| Shell/PowerShell syntax | Passed | Backup, restore, host inventory and Windows launch scripts parsed without execution. |
| Git whitespace check | Passed | `git diff --check`. |
| Tests and runtime evaluation | Deferred by user | No pytest, target-repository benchmark, model inference, UI runtime review, database integration test, Docker build, restore trial or OVH deployment was performed. |

The Vite build reports a bundle-size warning: the main JavaScript bundle is approximately 2.21 MB before gzip. This does not prevent compilation; splitting the graph/diagram tooling is a later performance task.

Static review repaired project-router registration, document/root identity and versioning mismatches, credential-path exclusions, source redaction, and the stopped-container restore workflow. These repairs still require runtime verification when testing resumes.

The source archive preserves the upstream tests and license, the original master plan, implementation/governance documents, launch/deployment files, and compiled frontend assets. It excludes Git internals, dependency directories, local environments, caches, application data and private env files.

Full plan completion requires the remaining software in `PLAN_STATUS.md`, the chosen target repository and manual, an inference configuration suited to OVH, and the deferred acceptance checks. This build does not establish that the assistant deeply understands an unavailable project.
