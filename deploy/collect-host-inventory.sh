#!/usr/bin/env bash
set -euo pipefail

# Prints capacity/version facts only. It never reads env files, process env,
# Docker container configuration, credentials, or user home files.

section() {
  printf '\n## %s\n' "$1"
}

section 'OS and kernel'
uname -srm
if [[ -r /etc/os-release ]]; then
  sed -n -E '/^(NAME|VERSION|VERSION_ID)=/p' /etc/os-release
fi

section 'CPU'
if command -v lscpu >/dev/null 2>&1; then
  lscpu | sed -n -E '/^(Architecture|CPU\(s\)|Model name|Thread\(s\) per core|Core\(s\) per socket|Socket\(s\)):/p'
else
  awk -F: '/^(processor|model name)[[:space:]]*:/ { print; count++ } END { if (count == 0) print "CPU details unavailable" }' /proc/cpuinfo
fi

section 'Memory'
if [[ -r /proc/meminfo ]]; then
  awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ { print }' /proc/meminfo
else
  printf 'Memory details unavailable\n'
fi

section 'Disks and mounts'
df -hT
if command -v lsblk >/dev/null 2>&1; then
  lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
fi

section 'GPU'
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
else
  printf 'NVIDIA GPU tooling unavailable; this does not rule out another accelerator.\n'
fi

section 'Container tooling'
if command -v docker >/dev/null 2>&1; then
  docker version --format 'Docker server: {{.Server.Version}}' 2>/dev/null || printf 'Docker daemon unavailable to this user.\n'
  docker compose version 2>/dev/null || printf 'Docker Compose plugin unavailable.\n'
else
  printf 'Docker unavailable.\n'
fi
