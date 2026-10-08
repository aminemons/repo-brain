# Repo Brain

A workspace for the repositories you work on. Create a bot for each repo, ask it to explain the code, and review proposed changes with their documentation.

Each bot has its own link, instructions, conversations, and change history. You choose which repositories to add. Bots use a free local coding model by default. You can also choose OpenAI and supply your own key for that session.

## Run on a server

On a Linux server with Docker, Docker Compose, Git, and OpenSSL installed:

```sh
git clone https://github.com/aminemons/repo-brain.git
cd repo-brain
bash scripts/setup-server.sh
```

From your computer, connect with `ssh -N -L 8000:127.0.0.1:8000 your-user@your-server`, then open [Bots](http://127.0.0.1:8000/bots). Enter the generated owner token from `deploy/server.env` in **Settings**. Local bots need no OpenAI key. The owner token is only the app login.

See [server setup](deploy/SERVER_SETUP.md) for private GitHub repositories, HTTPS, updates, and backups. The app and Najm renderer run as separate containers with persistent storage.

The server setup downloads Qwen2.5-Coder 0.5B on first start and stores it in a persistent Docker volume. Ollama has no published port. Local generation is limited to one request at a time and unloads the model after each response. The existing Azure VM is still subject to your Azure subscription costs; local inference adds no OpenAI charges.

For development without Docker, install [Ollama](https://ollama.com/), run `ollama pull qwen2.5-coder:0.5b`, and set `CODEWIKI_BOT_LOCAL_ENDPOINT=http://127.0.0.1:11434` in your environment.

## Local development

Requirements: Python 3.12+, Node.js 22+, Git, and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/aminemons/repo-brain.git
cd repo-brain
.\scripts\start-project-brain.ps1 -Setup
```

Open [localhost:8000](http://127.0.0.1:8000/bots). For later launches, run the script without `-Setup`.

To keep the app running after closing the terminal:

```powershell
.\scripts\start-project-brain.ps1 -Background
```

The launcher uses a hidden Windows task named `RepoBrain-Local-8000` and writes logs to `.run/`. Persistence through desktop sessions is not verified on every Windows installation. For continuous use, use the Linux server setup above. To stop the Windows task, run `Stop-ScheduledTask -TaskName RepoBrain-Local-8000`.

Manual setup works on other platforms:

```sh
uv sync --locked --extra docs
npm --prefix frontend ci
npm --prefix frontend run build
uv run --locked --extra docs python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Create your first bot

1. Open **Bots**, choose **Browse GitHub repositories**, or add a checkout or GitHub URL manually. Browsing uses the GitHub account configured on the server.
2. Create its bot and open the bot's link.
3. Keep **Local · free** selected, or choose OpenAI and enter your own API key.
4. Send a question. The first conversation indexes the repository automatically.

You can ask for an explanation, a lesson, an illustration, or a code change. Answers include repository evidence when available. Illustrate adds a Najm image of that evidence through the server renderer. Each question checks the code index for changes and rejects changed or deleted documentation excerpts. The watcher also tracks new commits for documentation review.

With Local selected, inference runs on the server and no model API key is needed. The bundled Qwen2.5-Coder 0.5B model fits small CPU servers; its answers and patches need careful review. For OpenAI, the key stays in page and request memory. Reloading the page clears it. API usage is billed to the account that owns the key. Selected repository excerpts and conversation context are sent to OpenAI for these requests.

For GitHub browsing and private repositories, configure `GH_TOKEN` on the machine running Repo Brain, or authenticate its GitHub CLI. The server account is separate from your desktop account. GitHub credentials remain on the server. Your OpenAI key gives access to the model; Git credentials give access to the repository.

## Changes and documentation

A change starts as a proposal you can inspect. Applying it creates a separate Git branch and worktree. Publishing opens a pull request for review. Merge it through your normal GitHub workflow.

The documentation watcher detects new commits and queues reviews. It can update clean GitHub checkouts cloned by the app. Update external local checkouts yourself. Documentation drafting uses the bot’s selected model; optional automatic drafting runs while the bot page is open.

Proposals use bounded file context. Sensitive paths and unsupported files are refused. The bot does not run your project's commands or tests, so verify changes before merging.

## Configuration

Copy `.env.example` to `.env` to configure paths, model settings, and access tokens. Configure `CODEWIKI_AUTH_TOKEN` before making the app remotely accessible. Enter that owner token in **Settings**. Bind to localhost for local use.

The existing graph, document search, learning maps, and local inference workflow are also available. The original model gateway supports local-only inference; repository bots support local Ollama inference and optional OpenAI keys.

Application data lives in `data/` and `storage/`. These directories, private environment files, and runtime logs are excluded from Git.

## Development

```sh
uv sync --locked --extra docs --extra dev
uv run pytest tests/backend/test_bots_api.py tests/backend/test_bot_changes.py
uv run mypy backend/app
npm --prefix frontend run build
```

The focused bot tests use temporary repositories and a stub model provider. They do not spend API credits or modify your repositories. See [the build report](docs/BUILD_REPORT.md) for verification results.

## Further reading

- [Bot guide](docs/BOT_USER_GUIDE.md)
- [Server setup](deploy/SERVER_SETUP.md)
- [Other deployment profiles](deploy/README.md)
- [Security](SECURITY.md)
- [Current plan status](docs/PLAN_STATUS.md)

Individual user accounts, sandboxed project command execution, and document embeddings remain unfinished. OVH deployment still needs validation in your environment.

## License

MIT. Built on [PorunC/CodeWiki](https://github.com/PorunC/CodeWiki), with its license preserved. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
