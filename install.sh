#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install the macOS Uninstall Cleanup skill into Codex or Claude Code.

Usage:
  ./install.sh codex [--copy|--symlink] [--force]
  ./install.sh claude [--copy|--symlink] [--force]

Defaults:
  codex  -> symlink into ~/.agents/skills, or ~/.codex/skills if that legacy directory already exists
  claude -> copy into ~/.claude/skills

Options:
  --copy      Copy files into the target directory.
  --symlink   Symlink the repository directory into the target directory.
  --force     Replace an existing installation at the target path.
EOF
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

tool="$1"
shift

method=""
force="false"
skill_name="macos-uninstall-cleanup"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy)
      method="copy"
      shift
      ;;
    --symlink)
      method="symlink"
      shift
      ;;
    --force)
      force="true"
      shift
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

case "${tool}" in
  codex)
    if [[ -z "${method}" ]]; then
      method="symlink"
    fi
    if [[ -d "${HOME}/.codex/skills" && ! -d "${HOME}/.agents/skills" ]]; then
      base_dir="${HOME}/.codex/skills"
      path_note="Using legacy Codex skill path because ~/.codex/skills already exists."
    else
      base_dir="${HOME}/.agents/skills"
      path_note="Using Codex user skill path ~/.agents/skills."
    fi
    invoke_note='Invoke in Codex with: $macos-uninstall-cleanup'
    ;;
  claude)
    if [[ -z "${method}" ]]; then
      method="copy"
    fi
    base_dir="${HOME}/.claude/skills"
    path_note="Using Claude Code personal skill path ~/.claude/skills."
    invoke_note='Invoke in Claude Code with: /macos-uninstall-cleanup'
    ;;
  *)
    echo "Unsupported target: ${tool}" >&2
    usage >&2
    exit 1
    ;;
esac

target_dir="${base_dir}/${skill_name}"
mkdir -p "${base_dir}"

if [[ -e "${target_dir}" || -L "${target_dir}" ]]; then
  if [[ "${force}" != "true" ]]; then
    echo "Target already exists: ${target_dir}" >&2
    echo "Re-run with --force to replace it." >&2
    exit 1
  fi
  rm -rf "${target_dir}"
fi

case "${method}" in
  symlink)
    ln -s "${repo_dir}" "${target_dir}"
    ;;
  copy)
    mkdir -p "${target_dir}"
    rsync -a \
      --exclude '.git/' \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude '.DS_Store' \
      "${repo_dir}/" "${target_dir}/"
    ;;
  *)
    echo "Unsupported method: ${method}" >&2
    exit 1
    ;;
esac

cat <<EOF
Installed ${skill_name} for ${tool}
Location: ${target_dir}
Method: ${method}
${path_note}
${invoke_note}

If the skill does not appear immediately, restart the app or start a new session.
EOF
