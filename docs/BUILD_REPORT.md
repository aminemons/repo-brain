# Build report

## Azure test deployment — 2026-10-07

Deployed application revision `fc15532` to the existing Azure Linux VM under `/opt/repo-brain`, using the private server Compose profile. The app and Najm containers are healthy. The existing Clipflow services remain healthy in their separate Compose project. App access uses an SSH tunnel; port 8000 is bound to the server's loopback interface.

Verified on the actual server:

- Owner authentication succeeds; unauthenticated bot API requests are rejected.
- The compiled frontend loads, and app-managed Git storage is writable.
- Najm renders a real PNG with decoded pixels and dimensions 1000 × 708.
- GitHub and OpenAI DNS/TLS connections succeed.
- Server GitHub credentials list the owner's repositories. The browser accepts the owner login and displays the GitHub picker with 30 loaded repositories.

No paid OpenAI request was made. The owner chooses a repository and supplies a model key to test a real answer. See [Azure access and maintenance](../deploy/AZURE_SETUP.md).

The underlying application checks passed in [Linux CI run 37599760251](https://github.com/aminemons/repo-brain/actions/runs/37599760251). Local inherited backend checks passed with 227 tests and 3 skipped; the later configuration-evidence regression checks passed with 9 tests. Pinned owner repositories `kaisser-explore` and `pfe` passed all six evidence questions without executing project commands.

## Repository and interface repairs — 2026-10-06

The bot interface now loads repository details and conversation history independently, offers retry controls, clears the previous transcript when switching conversations, and prevents overlapping conversation creation and message sends. Failed repository-plus-bot creation keeps the form values and explains how to reuse the registered repository. Authentication checks use a protected endpoint and typed HTTP errors; a rejected token is reported as a login problem.

Repository registration normalizes GitHub URL aliases and reuses existing checkouts. Cloning uses a temporary directory, a three-minute deadline, noninteractive credentials, and cleanup after failure. Remote URLs with embedded credentials are refused, and older metadata URLs are redacted before display. Index refresh and first-message indexing share a repository lock. Updating the server checks for untracked as well as tracked local source changes.

Secondary workspace pages load on demand. The main JavaScript entry fell from about 2.2 MB to 423 kB before gzip; the deferred diagram libraries still produce chunk-size warnings. Compatible dependency updates removed the high and moderate npm audit findings. Two low-severity findings remain in the Mermaid/KaTeX dependency chain.

Verification:

- 37 focused repository, chat, Git, illustration, and worker tests passed locally and in Linux CI. They cover owner/viewer access, bot history isolation, failed requests without incomplete turns, clone cleanup, URL alias reuse, and reviewed Git changes.
- Full backend type checks, focused Ruff, frontend lint, TypeScript, and production builds passed.
- A test-only Linux deployment uses the production API, database, index, authentication, and real Najm worker with deterministic model responses. The override is explicitly mounted by CI; ordinary server setup uses the production entrypoint.
- The complete Chromium journey passed in [Linux CI run 37522910146](https://github.com/aminemons/repo-brain/actions/runs/37522910146): token rejection and acceptance, two repository bots, chat success and failure, persisted and isolated history, a decoded protected Najm image, mobile overflow checks, and applying a reviewed README change on a separate branch.
- Chat follows new answers and loaded images until the reader scrolls up, then offers Jump to latest. The browser check confirms the new illustration decodes and the conversation scrolls to its latest reply. The composer keeps the full data-use guidance in a disclosure, leaving more space for messages.

The actual OVH installation, paid model responses using the owner's key, and real target-repository PR publication still need validation in the owner's environment. This update does not complete the unfinished features listed in `PLAN_STATUS.md`.

## Najm and Linux server setup — 2026-10-06

Implemented with GPT-6 Luna agents. The bot UI now offers Illustrate, keeps drafts after failed sends, and fetches protected PNGs with the owner token. The backend stores a bounded evidence map and provenance manifest beside each successful illustration. Failed provider/index requests leave no partial conversation turn; renderer failures preserve the text answer.

The Linux server profile fixes outbound access for explicit OpenAI requests, writable app-managed Git storage, GitHub CLI availability, private-repository synchronization, and PR publication to the selected origin repository. It runs the app and a pinned Najm renderer separately, with private SSH access by default and optional Caddy HTTPS.

Verification:

- 20 focused chat, Git, illustration, and worker tests passed locally. Model requests and PR publication use stubs; no API credits or target repositories were used.
- Full backend mypy passed across 260 files. Focused Ruff passed. Frontend lint, TypeScript, and Vite build passed; the existing large bundle warning remains.
- Linux CI built both images and started them with read-only root filesystems, non-root users, limited resources, and the renderer on an internal network.
- The real smoke check passed owner authentication, unauthorized-request rejection, frontend delivery, writable Git storage, and OpenAI/GitHub DNS and TLS connectivity.
- Najm rendered a genuine 1400 × 1000 PNG. Its revision header, chunk checksums, decompressed pixels, dimensions, and output size were checked. The .NET host layout was corrected after a native runtime-location error.

The latest workflow additionally uploads that PNG for visual review. This is Linux container verification; the actual OVH server and a response using the owner's OpenAI key remain untested. No application or native renderer was launched on the owner's PC during this update. Earlier Windows background-launch observations did not establish persistent operation through desktop sessions; use the server profile for continuous operation.

## Chat and Git fixes â€” 2026-10-05

Follow-up: the WMI-launched server also disappeared after the chat turn ended. Background startup now uses Windows Task Scheduler with an interactive, non-elevated principal and no triggers. The API health check and browser bot library loaded successfully after that change. The earlier cross-command check did not establish survival beyond the chat turn.

The local API had stopped. A bot package export also prevented startup after the latest edits. The chat API now indexes a fresh repository before retrieval and returns useful provider errors without exposing request credentials. The background PowerShell launcher was exercised successfully against the local API.

Integration tests found an empty worktree index during change application. Seeding it with the base commit now preserves untouched tracked files. The regression tests cover that behavior, optimistic checks, documentation completion after merge, deduplication and batching, commit detection, and a stubbed publication path.

Verification so far:

- Chat API integration test passed with a temporary repository and stub OpenAI provider. It covers registration, bot uniqueness, first-chat indexing, persistence, `store=False`, refresh, model error handling, and absence of the key from SQLite/WAL.
- Six Git workflow integration tests passed using temporary repositories; publishing is stubbed.
- The combined chat and Git regression suite passed: seven tests in 48.84 seconds. FastAPI's inherited TestClient emits an httpx deprecation warning.
- Full backend mypy passed for 259 source files. Focused bot Ruff checks passed.
- The detached local server returned `{"status":"ok"}` from `/api/health` and binds to `127.0.0.1:8000`.
- The final frontend build and focused ESLint passed. Browser review covered the bot library, conversation/settings navigation, saved model changes, connection failure reporting, and the mobile composer at 390 Ã— 844 with no horizontal page overflow.
- The Windows launcher uses a hidden WMI worker to detach the server from the launching tool session. The root-launched instance remained healthy across later build, Git, browser, and packaging commands.
- The first GitHub workflow run passed. It checks the bot backend, all backend types, the focused regression suite, and frontend compilation.

The inherited full Ruff check reports existing violations across the base application and tests. GitHub's default workflow explicitly checks the bot modules and focused regression tests, all backend types, and the frontend build. The inherited full test suite remains an optional manual run. No paid model request, real target-repository push/PR, OVH deployment, or sandboxed project command execution was performed.

## Dedicated bot release â€” 2026-10-04

The repository bot implementation was finished with GPT-6 Luna agents. It adds a bot library and stable bot links, separate persisted conversations, editable per-bot settings, request-only OpenAI key handling, Explain/Teach modes, knowledge refresh, reviewed file proposals, isolated Git branches and pull-request publication. Documentation tracking detects commit changes, refreshes knowledge, and supports reviewable drafts in batches of up to 20 changed source paths. Optional automatic drafting runs only while the bot page is open with its key entered.

Final checks for this update:

- Frontend TypeScript/Vite build and focused ESLint passed after the refresh and batching UI changes.
- Full backend mypy passed: 259 source files.
- Ruff passed for the new bot APIs, schemas, services and changed application/config/security modules.
- Python compilation, dependency lock consistency (135 packages) and Git whitespace checks passed.
- The local application started successfully on `http://127.0.0.1:8000`; Uvicorn logged application startup complete and listening. The earlier server instance was replaced.

The build retains the existing JavaScript chunk-size warning. No automated tests, browser interaction tests, model requests, target-repository analysis, real change branches, or GitHub pull requests were run for this update. Startup confirms that the application launches; it does not verify the full bot or Git workflow.

Initial access uses the application's shared owner token. Individual user accounts, a process sandbox for running project commands, target evaluations, and OVH deployment remain unfinished. Proposals use bounded whole-file text edits and refuse unsupported/sensitive inputs. Tests remain deferred by the owner's direction. The source ZIP includes the compiled interface and excludes local data, environments and credentials.

## Initial implementation â€” 2026-10-03

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
