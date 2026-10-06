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
    "${compose[@]}" exec -T app python - < scripts/smoke-server.py
    ;;
  *) echo 'Usage: bash scripts/server.sh {config|up|stop|status|logs|update|check}' >&2; exit 2 ;;
esac
