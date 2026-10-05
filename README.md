# Repo Brain

A workspace for the repositories you work on. Create a bot for each repo, ask it to explain the code, and review proposed changes with their documentation.

Each bot has its own link, instructions, conversations, and change history. You choose which repositories to add. Model requests use the OpenAI API key you enter for that session.

## Run locally

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

The launcher waits for a healthy API and writes its PID and logs to `.run/`.

Manual setup works on other platforms:

```sh
uv sync --locked --extra docs
npm --prefix frontend ci
npm --prefix frontend run build
uv run --locked --extra docs python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Create your first bot

1. Open **Bots** and add a local checkout or a GitHub repository URL.
2. Create its bot and open the bot's link.
3. Enter your OpenAI API key and choose a model your API account can access.
4. Send a question. The first conversation indexes the repository automatically.

You can ask for an explanation, a lesson, or a code change. Answers include repository evidence when available. Refresh knowledge after local changes; the watcher also tracks new commits.

The key stays in page and request memory. Reloading the page clears it. API usage is billed to the account that owns the key. Selected repository excerpts and conversation context are sent to OpenAI for these requests.

For private GitHub repositories, authenticate Git on the machine running Repo Brain. Your OpenAI key gives access to the model; Git credentials give access to the repository.

## Changes and documentation

A change starts as a proposal you can inspect. Applying it creates a separate Git branch and worktree. Publishing opens a pull request for review. Merge it through your normal GitHub workflow.

The documentation watcher detects new commits and queues reviews. It can update clean GitHub checkouts cloned by the app. Update external local checkouts yourself. Documentation drafting needs your API key; optional automatic drafting runs while the bot page is open.

Proposals use bounded file context. Sensitive paths and unsupported files are refused. The bot does not run your project's commands or tests, so verify changes before merging.

## Configuration

Copy `.env.example` to `.env` to configure paths, model settings, and access tokens. Configure `CODEWIKI_AUTH_TOKEN` before making the app remotely accessible. Enter that owner token in **Settings**. Bind to localhost for local use.

The existing graph, document search, learning maps, and local inference workflow are also available. The original model gateway supports local-only inference; repository bots use the explicitly supplied OpenAI key.

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
- [Deployment](deploy/README.md)
- [Security](SECURITY.md)
- [Current plan status](docs/PLAN_STATUS.md)

Individual user accounts, sandboxed project command execution, and document embeddings remain unfinished. Hosting on OVH and live model responses need validation in your environment.

## License

MIT. Built on [PorunC/CodeWiki](https://github.com/PorunC/CodeWiki), with its license preserved. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
