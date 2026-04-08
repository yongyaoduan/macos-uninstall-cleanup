#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install a user-scoped sudo timestamp policy for the macos-uninstall-cleanup skill.

Usage:
  sudo ./install_sudo_cache_mode.sh [--user USER] [--balanced|--day|--never-expire|--timeout MINUTES]

Modes:
  --balanced       Share sudo auth across PTYs for 4 hours. Recommended.
  --day            Share sudo auth across PTYs for 24 hours.
  --never-expire   Never expire automatically until reboot, or until you run sudo -k/-K.
  --timeout N      Custom timeout in minutes. Negative values never expire.

This writes a drop-in under /etc/sudoers.d scoped to one user:
  Defaults:USER timestamp_type=global
  Defaults:USER timestamp_timeout=N
EOF
}

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

target_user="${SUDO_USER:-${USER}}"
timeout="240"
mode="balanced"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      target_user="${2:-}"
      shift 2
      ;;
    --balanced)
      timeout="240"
      mode="balanced"
      shift
      ;;
    --day)
      timeout="1440"
      mode="day"
      shift
      ;;
    --never-expire)
      timeout="-1"
      mode="never-expire"
      shift
      ;;
    --timeout)
      timeout="${2:-}"
      mode="custom"
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

if [[ -z "${target_user}" ]] || ! id "${target_user}" >/dev/null 2>&1; then
  echo "Target user does not exist: ${target_user}" >&2
  exit 1
fi

if ! [[ "${timeout}" =~ ^-?[0-9]+$ ]]; then
  echo "Timeout must be an integer number of minutes." >&2
  exit 1
fi

target_home="$(python3 - "${target_user}" <<'PY'
import pwd
import sys

print(pwd.getpwnam(sys.argv[1]).pw_dir)
PY
)"
target_group="$(id -gn "${target_user}")"

dropin="/etc/sudoers.d/codex-macos-uninstall-cleanup-${target_user}"
tmp_file="$(mktemp)"
tmp_state="$(mktemp)"
trap 'rm -f "${tmp_file}" "${tmp_state}"' EXIT

cat > "${tmp_file}" <<EOF
Defaults:${target_user} timestamp_type=global
Defaults:${target_user} timestamp_timeout=${timeout}
EOF

visudo -cf "${tmp_file}" >/dev/null
install -o root -g wheel -m 0440 "${tmp_file}" "${dropin}"
visudo -cf "${dropin}" >/dev/null

state_dir="${target_home}/.codex/state/macos-uninstall-cleanup"
state_file="${state_dir}/sudo_cache_mode.json"
install -d -o "${target_user}" -g "${target_group}" -m 0755 "${state_dir}"
cat > "${tmp_state}" <<EOF
{"enabled": true, "mode": "${mode}", "timestamp_timeout": ${timeout}}
EOF
install -o "${target_user}" -g "${target_group}" -m 0644 "${tmp_state}" "${state_file}"

cat <<EOF
Installed ${dropin}
Mode: ${mode}
User: ${target_user}
timestamp_type: global
timestamp_timeout: ${timeout}
State file: ${state_file}

This reduces repeated password or Touch ID prompts across new PTYs.
Negative timeout means the sudo ticket will not expire automatically until reboot.
To invalidate the current sudo ticket immediately, run: sudo -k or sudo -K
To remove this policy later, run:
  sudo $(dirname "$0")/remove_sudo_cache_mode.sh --user ${target_user}
EOF
