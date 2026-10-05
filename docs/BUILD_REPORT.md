# Build report

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
