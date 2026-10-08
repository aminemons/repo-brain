# Run Repo Brain on your server

The server runs the application and a separate Najm image renderer. Docker keeps them running after you disconnect. Repositories, conversations, and generated images live in persistent volumes.

## Install and start

Use a Linux x86-64 server with Git, OpenSSL, Docker Engine, and the Docker Compose plugin installed. Docker must be usable by your login user. The default limits are 2 GB for the app, 512 MB for Najm, and 1400 MB for local inference; allow additional memory for building the images and indexing large repositories.

Clone the private repository using your GitHub account, or extract the supplied archive and enter its `project-brain` directory:

```sh
git clone https://github.com/aminemons/repo-brain.git
cd repo-brain
bash scripts/setup-server.sh
```

The first build downloads dependencies and the pinned Najm source. Setup creates `deploy/server.env` with a random owner token and restrictive permissions. It then builds the app and renderer, starts all three services, downloads the local coding model, and checks authentication, writable repository storage, an actual Najm PNG render, and connectivity to GitHub and OpenAI. It makes no paid model request.

If setup fails, inspect `bash scripts/server.sh logs`, correct the reported problem, and run `bash scripts/server.sh up` again. A healthy renderer HTTP endpoint alone does not prove rendering works; the Linux CI smoke check renders a real PNG with the same container restrictions.

## Private access through SSH

On your own computer, keep this command running, replacing the SSH login:

```sh
ssh -N -L 8000:127.0.0.1:8000 your-user@your-server
```

Open <http://127.0.0.1:8000/bots>. The app port is bound to the server's loopback interface. SSH provides the encrypted connection; no public app port or domain is required.

On the server, read `CODEWIKI_AUTH_TOKEN` in `deploy/server.env`. Enter that value in the app's **Settings** page. Keep it private: this is your application login token.

## Connect a repository and model

1. Choose **Browse GitHub repositories** to select from the server's GitHub account, or add a repository URL manually, then create its bot. Each repository has its own bot link and history. Browsing an existing bot opens its link without creating a duplicate.
2. Keep **Local · free** selected to use Qwen2.5-Coder without an API key. Choose OpenAI only if you want to supply your own key.
3. Send a question. The app indexes the selected repository before answering.
4. Select **Illustrate** for an additional Najm image of the cited evidence. If rendering fails, the normal answer stays available.

Your OpenAI key stays in page/request memory and clears on reload. It is different from the owner token and GitHub credentials.

Paste the repository's root URL, such as `https://github.com/owner/project`, rather than a file or branch page. Different GitHub URL spellings reuse the same registered checkout. A failed clone is cleaned up so you can correct GitHub access and retry. Cloning stops after three minutes; a large repository may need a checkout mounted on the server instead.

If a message fails, its draft stays in the composer. Check the reported error and selected model (and your API key when using OpenAI), then send it again. A failed request does not add an incomplete turn to conversation history.

For private repositories or publishing branches and pull requests, put a GitHub token in `GH_TOKEN` in `deploy/server.env`, then run `bash scripts/server.sh up`. Give it access only to the repositories you choose, with Contents and Pull requests write permissions when publishing changes. The application image includes Git and the GitHub CLI. A path on your own PC is unavailable to the server; use a GitHub URL or deliberately mount a server checkout.

## Optional HTTPS domain

Point a domain to the server and allow inbound TCP ports 80 and 443. On a fresh installation:

```sh
bash scripts/setup-server.sh --domain brain.example.com
```

For an existing installation, set `PUBLIC_DOMAIN=brain.example.com` in `deploy/server.env`, then run `bash scripts/server.sh up`. Caddy obtains and renews certificates. Open `https://brain.example.com/bots` and use the same owner token. Leave `PUBLIC_DOMAIN` empty for SSH-only access.

## Maintenance

```sh
bash scripts/server.sh status
bash scripts/server.sh check
bash scripts/server.sh logs
bash scripts/server.sh stop
```

For a Git clone, `bash scripts/server.sh update` pulls the next commit and rebuilds. Preserve local source changes before updating. For an archive installation, stop the app and replace the source files, keeping `deploy/server.env`, then start again. Named Docker volumes survive a stop and rebuild.

Back up both `app-data` and `app-storage` volumes while the app is stopped; the first includes SQLite and the second includes checkouts, indexes, and images. Back up the private environment file separately. Never use `docker compose down --volumes` unless you intend to delete the stored data.

Najm receives bounded labels and verified relationships through an internal network. It has no repository mount, API key, or outbound network. The app needs outbound access to GitHub and OpenAI. The server profile includes a private Ollama service with a persistent model volume. It publishes no inference port and does not receive GitHub or OpenAI credentials. The older `compose.project-brain.yml` is a separate deployment profile; use `compose.server.yml` for this repository-bot setup.
