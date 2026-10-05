#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
env_file="$script_dir/project-brain.env"
compose_file="$repo_root/compose.project-brain.yml"
backup_root="${1:-${PROJECT_BRAIN_BACKUP_DIR:-$repo_root/../project-brain-backups}}"

if [[ ! -r "$env_file" ]]; then
  printf 'Deployment env file is missing: %s\n' "$env_file" >&2
  exit 1
fi
mkdir -p -- "$backup_root"
chmod 700 -- "$backup_root"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
temporary_dir="$(mktemp -d "$backup_root/.project-brain-backup.XXXXXXXX")"
final_dir="$backup_root/project-brain-$stamp"

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  if [[ -d "$temporary_dir" ]]; then
    rm -rf -- "$temporary_dir"
  fi
}
trap cleanup EXIT

# pg_dump uses a consistent database snapshot. Storage may change while it is
# archived; pause users at the reverse proxy first if a cross-store checkpoint
# is required.
compose exec -T postgres sh -ec 'pg_dump --no-owner --no-acl -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$temporary_dir/database.dump"
compose exec -T codewiki tar --no-same-owner -C /app/storage -czf - . > "$temporary_dir/project-storage.tar.gz"

{
  printf 'created_utc=%s\n' "$stamp"
  printf 'database=database.dump\n'
  printf 'application_storage=project-storage.tar.gz\n'
  printf 'repository_source=not_included; back up from its Git/host source separately\n'
  if command -v git >/dev/null 2>&1; then
    git -C "$repo_root" rev-parse HEAD 2>/dev/null | sed 's/^/deployment_commit=/' || true
  fi
} > "$temporary_dir/manifest.txt"

if [[ -e "$final_dir" ]]; then
  printf 'Backup destination already exists: %s\n' "$final_dir" >&2
  exit 1
fi
mv -- "$temporary_dir" "$final_dir"
temporary_dir=''
printf 'Backup created at %s\n' "$final_dir"
