#!/usr/bin/env bash
set -euo pipefail
project_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_directory"
[[ -f deploy/server.env ]] || { echo 'Run bash scripts/setup-server.sh first.' >&2; exit 1; }
compose=(docker compose --env-file deploy/server.env -f compose.server.yml)
if grep -Eq '^PUBLIC_DOMAIN=[a-zA-Z0-9][a-zA-Z0-9.-]+$' deploy/server.env; then
  compose+=(-f compose.server.https.yml)
fi
case "${1:-status}" in
  config) "${compose[@]}" config --quiet ;;
  up) "${compose[@]}" up --build --detach --wait --wait-timeout 300 ;;
  stop) "${compose[@]}" stop ;;
  status) "${compose[@]}" ps ;;
  logs) "${compose[@]}" logs --tail 100 app najm ;;
  update)
    git diff --quiet && git diff --cached --quiet || { echo 'Commit or preserve local source changes before updating.' >&2; exit 1; }
    git pull --ff-only
    "${compose[@]}" up --build --detach --wait --wait-timeout 300 ;;
  check)
    "${compose[@]}" exec -T app python - <<'PY'
import json
import os
import shutil
import urllib.error
import urllib.request

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/bots",
    headers={"Authorization": "Bearer " + os.environ["CODEWIKI_AUTH_TOKEN"]},
)
with urllib.request.urlopen(request, timeout=10) as response:
    bots = json.load(response)
print("Application API and owner authentication: OK")
print("Registered bots:", len(bots["bots"]))
with urllib.request.urlopen("http://najm:8080/health", timeout=10) as response:
    renderer = json.load(response)
print("Najm worker health:", renderer.get("status", "unknown"))
for name, url in (("OpenAI", "https://api.openai.com/"), ("GitHub", "https://github.com/")):
    try:
        urllib.request.urlopen(url, timeout=10).close()
    except urllib.error.HTTPError:
        pass
    print(name + " DNS/TLS connectivity: OK")
if not shutil.which("gh"):
    raise SystemExit("GitHub CLI is missing from the application image.")
print("GitHub CLI: installed")
print("No model request was made. Enter your OpenAI key and an accessible model ID in a bot to test an answer.")
PY
    ;;
  *) echo 'Usage: bash scripts/server.sh {config|up|stop|status|logs|update|check}' >&2; exit 2 ;;
esac
