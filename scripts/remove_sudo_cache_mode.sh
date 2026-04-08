#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Remove the user-scoped sudo timestamp policy installed for the macos-uninstall-cleanup skill.

Usage:
  sudo ./remove_sudo_cache_mode.sh [--user USER]
EOF
}

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

target_user="${SUDO_USER:-${USER}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      target_user="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${target_user}" ]]; then
  echo "Target user is required." >&2
  exit 1
fi

target_home="$(python3 - "${target_user}" <<'PY'
import pwd
import sys

print(pwd.getpwnam(sys.argv[1]).pw_dir)
PY
)"
state_dir="${target_home}/.codex/state/macos-uninstall-cleanup"
state_file="${state_dir}/sudo_cache_mode.json"

dropin="/etc/sudoers.d/codex-macos-uninstall-cleanup-${target_user}"
if [[ -e "${dropin}" ]]; then
  rm -f "${dropin}"
  echo "Removed ${dropin}"
else
  echo "No drop-in found at ${dropin}"
fi

if [[ -e "${state_file}" ]]; then
  rm -f "${state_file}"
  rmdir "${state_dir}" 2>/dev/null || true
  echo "Removed ${state_file}"
fi

echo "Run sudo -K if you also want to invalidate any currently cached sudo ticket."
