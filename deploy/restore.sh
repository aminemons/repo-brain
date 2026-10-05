#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
env_file="$script_dir/project-brain.env"
compose_file="$repo_root/compose.project-brain.yml"

if [[ $# -ne 2 || "$2" != '--confirm' ]]; then
  printf 'Usage: %s BACKUP_DIRECTORY --confirm\n' "$0" >&2
  printf 'This replaces the Project Brain database and application storage.\n' >&2
  exit 2
fi
backup_dir="$(cd -- "$1" && pwd)"
if [[ ! -r "$env_file" ]]; then
  printf 'Deployment env file is missing: %s\n' "$env_file" >&2
  exit 1
fi
if [[ ! -f "$backup_dir/database.dump" || ! -f "$backup_dir/project-storage.tar.gz" ]]; then
  printf 'Backup directory must contain database.dump and project-storage.tar.gz.\n' >&2
  exit 1
fi

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}
run_codewiki() {
  compose run --rm --no-deps -T -e RESTORE_SUFFIX="$restore_suffix" codewiki "$@"
}

restart_app=0
cleanup() {
  status=$?
  if [[ "$status" -ne 0 && "$restart_app" == 1 ]]; then
    printf 'Restore did not complete; codewiki remains stopped. Review the error before restarting it.\n' >&2
  fi
}
trap cleanup EXIT

# Stage storage in the persistent named volume before replacing the database.
# The app is stopped, so use one-off containers rather than `compose exec`.
# `/app/storage` is a volume mountpoint and must remain in place.
restore_suffix="$(date -u +%Y%m%dT%H%M%SZ)"
compose stop codewiki
restart_app=1
run_codewiki sh -ec 'staging="/app/storage/.restore-staging-$RESTORE_SUFFIX"; test ! -e "$staging" && mkdir -p "$staging" && tar --no-same-owner --no-same-permissions -xzf - -C "$staging"' < "$backup_dir/project-storage.tar.gz"

compose exec -T postgres sh -ec 'pg_restore --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$backup_dir/database.dump"
run_codewiki sh -ec 'staging="/app/storage/.restore-staging-$RESTORE_SUFFIX"; previous="/app/storage/.pre-restore-$RESTORE_SUFFIX"; test -d "$staging"; mkdir -p "$previous"; find /app/storage -mindepth 1 -maxdepth 1 ! -name ".pre-restore-$RESTORE_SUFFIX" ! -name ".restore-staging-$RESTORE_SUFFIX" -exec mv -- {} "$previous" \;; tar -C "$staging" -cf - . | tar -C /app/storage -xpf -; rm -rf -- "$staging"'
compose start codewiki
restart_app=0
printf 'Restore completed from %s\n' "$backup_dir"
