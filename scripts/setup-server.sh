#!/usr/bin/env bash
set -euo pipefail

project_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_directory"
umask 077

domain=""
prepare_only=false
while (($#)); do
  case "$1" in
    --domain)
      [[ $# -ge 2 ]] || { echo 'Usage: setup-server.sh [--domain hostname] [--prepare-only]' >&2; exit 2; }
      domain="$2"; shift 2 ;;
    --prepare-only) prepare_only=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ -n "$domain" ]] && [[ ! "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]]; then
  echo 'Use a DNS hostname without a scheme, port, path, or spaces.' >&2
  exit 2
fi
for command in docker openssl; do
  command -v "$command" >/dev/null || { echo "Install $command on the Linux server before running setup." >&2; exit 1; }
done
docker compose version >/dev/null

if [[ ! -f deploy/server.env ]]; then
  owner_token="$(openssl rand -hex 32)"
  {
    printf 'CODEWIKI_AUTH_TOKEN=%s\n' "$owner_token"
    printf 'APP_PORT=8000\nAPP_MEMORY_LIMIT=2g\nAPP_CPU_LIMIT=2\n'
    printf 'NAJM_MEMORY_LIMIT=512m\nNAJM_CPU_LIMIT=1\nGH_TOKEN=\n'
    printf 'PUBLIC_DOMAIN=%s\n' "$domain"
  } > deploy/server.env
  unset owner_token
  echo 'Created private deployment settings in deploy/server.env.'
else
  echo 'Keeping the existing deploy/server.env and owner token.'
  if [[ -n "$domain" ]]; then
    echo 'An environment already exists. Set PUBLIC_DOMAIN there before using HTTPS.'
  fi
fi
chmod 600 deploy/server.env
echo 'Enter CODEWIKI_AUTH_TOKEN from deploy/server.env in the app Settings page.'
echo 'For private GitHub repositories, set GH_TOKEN in that file before starting.'
echo 'OpenAI keys are entered in the bot page and are not deployment secrets.'
if [[ "$prepare_only" == true ]]; then
  bash scripts/server.sh config
else
  bash scripts/server.sh up
  bash scripts/server.sh check
fi
