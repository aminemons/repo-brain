# Project Brain deployment

This Compose profile is a production-oriented starting point for one private repository. It puts the application behind Caddy, keeps PostgreSQL and model services on an internal network, mounts the configured repository and documentation roots read-only, requires an owner token and database password, and enables local-only model routing by default.

It is not ready to start until the actual repository path, DNS name, secrets, OVH capacity, and a supported local model endpoint are configured. The target application repository and the project manual have not yet been supplied. No performance or security acceptance claim is implied by this template.

## Prepare the host

1. Install a supported Docker Engine and Compose plugin on the OVH host. Confirm that the host's firewall allows inbound TCP 80 and 443; allow UDP 443 only if HTTP/3 is wanted.
2. Point the chosen DNS name at the host. Use a dedicated deployment checkout for this repository.
3. Place the target repository and manual on the host. Set `PROJECT_REPO_PATH` to the repository and `DOCUMENTATION_PATH` to the manual directory; it defaults to `<repository>/docs`. Do not use paths that contain production credentials or data files that should not be indexed.
4. Collect host details before selecting a model. The inventory script reports OS, CPU, memory, disks, GPU details when available, and container versions. Review its output before sharing it; it does not read deployment environment files or print secrets.
5. Copy `deploy/project-brain.env.example` to a private file such as `deploy/project-brain.env`. Replace the domain and source paths, and generate separate random values for `POSTGRES_PASSWORD` and `CODEWIKI_AUTH_TOKEN`. Keep the file out of version control and restrict its filesystem permissions to the deployment operator.
6. Set `POSTGRES_IMAGE`, `CADDY_IMAGE`, and `OLLAMA_IMAGE` to pinned versions reviewed for the host. Keep model fields empty until the host is inventoried and a local model is selected. A blank model configuration means model-backed features are not ready.

For example, on the Linux host:

```bash
cp deploy/project-brain.env.example deploy/project-brain.env
chmod 600 deploy/project-brain.env
openssl rand -hex 32
bash deploy/collect-host-inventory.sh > host-inventory.txt
```

Run the random generator twice and put each value in a different secret field.

The sample uses a hexadecimal database password so the PostgreSQL URL assembled by Compose does not need URL-encoding. If changing its format, URL-encode reserved characters before placing the value in `CODEWIKI_DATABASE_URL`. Image tags in the example are placeholders; pin reviewed tags or digests before starting services.

## Start services

From the repository root on the Linux host, first review the rendered Compose configuration and confirm that the repository mount resolves to the intended directory. Then start the production services:

```bash
docker compose --env-file deploy/project-brain.env -f compose.project-brain.yml config --quiet
docker compose --env-file deploy/project-brain.env -f compose.project-brain.yml up -d --build
```

Caddy obtains and renews certificates for `PUBLIC_DOMAIN`. The application is not published on a host port; only Caddy binds ports 80 and 443. PostgreSQL and the optional Ollama service are not published on host ports.

The optional Ollama profile is CPU-oriented and does not imply acceptable performance on a particular OVH server. Enable it only after selecting a tested image and model:

```bash
docker compose --env-file deploy/project-brain.env -f compose.project-brain.yml --profile ollama up -d ollama
docker compose --env-file deploy/project-brain.env -f compose.project-brain.yml exec ollama ollama pull <approved-model>
```

Then set the model profile's endpoint to `http://ollama:11434` and choose a model identifier supported by the pinned CodeWiki/LiteLLM version. Restart the app after changing its environment. Do not add external provider endpoints while `CODEWIKI_LOCAL_ONLY=true`.

## Access and privacy

The owner token is sent as an HTTP Bearer token for protected API operations. `CODEWIKI_VIEWER_TOKEN`, when configured, is intended for read-only access: besides GET/HEAD, it may POST only `/api/repos/{id}/ask`, `/api/repos/{id}/graph/explore`, `/api/repos/{id}/graph/affected`, and `/api/repos/{id}/graphrag/retrieve`. Confirm that the API and browser UI enforce these role boundaries before sharing the site. Never put owner/provider tokens in a URL, browser local storage, source code, or logs.

The application, PostgreSQL, and optional Ollama service use private internal networks. Caddy connects to the public `edge` network and a separate internal `proxy` network; it does not join the database network. The application has no general outbound network route in this local-only Compose topology. To enable a remote model later, the operator must deliberately change the network topology and allow only the required provider egress, in addition to setting both privacy controls. The repository is mounted read-only at `/workspace/project`; documentation is mounted read-only at `/workspace/documentation`. The application container drops Linux capabilities, runs with a read-only root filesystem, and has a size-limited temporary filesystem. These controls do not replace a host review or the future command-sandbox design required for write mode.

`CODEWIKI_LOCAL_ONLY=true` takes precedence over the privacy-mode selector and blocks external model destinations. To opt into an external provider, an operator must set `CODEWIKI_LOCAL_ONLY=false` and select a non-local privacy mode. In `sanitized` mode, outbound prompts include the redacted user question (up to 1,000 characters) and an allowlisted subset of graph metadata; source excerpts are omitted and behavior should be treated as unverified. `relevant_excerpts` sends the retrieved evidence after redaction, bounded by `CODEWIKI_EXTERNAL_EXCERPT_MAX_CHARS`. `maximum_intelligence` sends redacted relevant evidence without that character cap. None of these modes automatically escalates to a provider; the configured model endpoint still has to be selected. Review the exact privacy implementation and provider logging before enabling hybrid use.

## Operations

Inspect status and logs:

```bash
docker compose --env-file deploy/project-brain.env -f compose.project-brain.yml ps
docker compose --env-file deploy/project-brain.env -f compose.project-brain.yml logs --tail 200 codewiki caddy postgres
```

Back up PostgreSQL and `project-storage` before upgrades. The indexed graph can be regenerated from Git and the manual, but approved mappings, artifacts, and audit history may not be reproducible. The helper writes a restricted plaintext backup outside the checkout by default; encrypt it before copying off-host and test restoration before relying on it. Pause writes at the reverse proxy first if a single cross-store checkpoint is required.

```bash
bash deploy/backup.sh
bash deploy/restore.sh /secure/path/project-brain-YYYYMMDDTHHMMSSZ --confirm
```

Restore replaces the database. It stages storage in the named volume before the database import and keeps the previous application storage in a `storage/.pre-restore-*` directory. Only restore archives created by this deployment should be used; treat archives from other sources as untrusted. If restore fails after the app is stopped, the script leaves the app stopped so the operator can inspect the database state before restarting.

Upgrade by reviewing the source diff, pinned dependency changes, database migrations, and backup first. Then rebuild and recreate services from a known revision. Do not run automatic image updates for production.

## Still required before production acceptance

- Complete backend and UI auth flows and confirm viewer tokens cannot access write/admin endpoints.
- Validate root and symlink confinement against the actual target repository, including ignored/generated paths and secret exclusions.
- Inventory the manual and OVH hardware; choose and benchmark a local model.
- Run and report build, lint, and security checks as implementation proceeds. Tests remain deferred by the user's direction; record that deferral rather than reporting a pass.
- Verify backups, restores, TLS renewal, health alerts, rate limits, and incident handling on the actual host.
- Complete the target-specific evidence benchmark before claiming Project Brain understands the project.
# Dedicated bots and outbound services

The repository bot workflow uses the OpenAI key supplied for each request. The default Compose topology confines the application to internal networks, so OpenAI requests and GitHub fetch/push operations will fail until the operator configures deliberate outbound access. The local Windows launch has ordinary host network access.

The template mounts the target checkout read-only. Preparing a branch needs writable Git metadata; use an application-managed clone under writable storage for that workflow. An OpenAI API key does not grant GitHub permissions. Install and authenticate Git/GitHub CLI separately before publishing pull requests. The watcher can fast-forward clean application-managed GitHub clones when enabled; it never resets an owner-maintained checkout.

Initial bot access uses the shared owner token. Individual accounts, process-isolated execution of project commands, and server-specific deployment validation remain outside this release. See `docs/BOT_USER_GUIDE.md`.

