#!/usr/bin/env python3
import json
import os
import pwd
import re
import subprocess
from pathlib import Path


def target_user():
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "unknown"


def target_home(user: str) -> Path:
    try:
        return Path(pwd.getpwnam(user).pw_dir)
    except KeyError:
        return Path.home()


def mode_from_timeout(timeout):
    if timeout == -1:
        return "never-expire"
    if timeout == 240:
        return "balanced"
    if timeout == 1440:
        return "day"
    if isinstance(timeout, int):
        return "custom"
    return None


def parse_dropin(dropin: Path):
    try:
        content = dropin.read_text()
    except OSError:
        try:
            result = subprocess.run(
                ["sudo", "-n", "cat", str(dropin)],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        content = result.stdout

    timeout = None
    timestamp_type = None
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        timeout_match = re.match(r"Defaults:[^ ]+\s+timestamp_timeout=(-?\d+)\s*$", stripped)
        if timeout_match:
            timeout = int(timeout_match.group(1))
            continue
        type_match = re.match(r"Defaults:[^ ]+\s+timestamp_type=([a-zA-Z_]+)\s*$", stripped)
        if type_match:
            timestamp_type = type_match.group(1)

    if timeout is None and timestamp_type is None:
        return None

    return {
        "timestamp_timeout": timeout,
        "timestamp_type": timestamp_type,
        "mode": mode_from_timeout(timeout),
    }


def load_state_file(state_file: Path):
    if not state_file.exists():
        return None
    try:
        state = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return state if isinstance(state, dict) else None


def main():
    user = target_user()
    home = target_home(user)
    state_file = home / ".codex/state/macos-uninstall-cleanup/sudo_cache_mode.json"
    dropin = Path("/etc/sudoers.d") / f"codex-macos-uninstall-cleanup-{user}"

    result = {
        "target_user": user,
        "enabled": False,
        "mode": None,
        "timestamp_timeout": None,
        "source": "none",
        "state_file": str(state_file),
        "dropin": str(dropin),
    }

    state = load_state_file(state_file)
    dropin_state = parse_dropin(dropin) if dropin.exists() else None

    if dropin_state:
        result.update(
            {
                "enabled": True,
                "mode": dropin_state.get("mode"),
                "timestamp_timeout": dropin_state.get("timestamp_timeout"),
                "timestamp_type": dropin_state.get("timestamp_type"),
                "source": "dropin",
            }
        )
        if state:
            result["state_file_enabled"] = bool(state.get("enabled", True))
            result["state_file_mode"] = state.get("mode")
            result["state_file_timestamp_timeout"] = state.get("timestamp_timeout")
    elif dropin.exists():
        result.update(
            {
                "enabled": True,
                "source": "dropin_name",
            }
        )
        if state:
            result["mode"] = state.get("mode")
            result["timestamp_timeout"] = state.get("timestamp_timeout")
            result["state_file_enabled"] = bool(state.get("enabled", True))
    elif state:
        result.update(
            {
                "enabled": False,
                "mode": state.get("mode"),
                "timestamp_timeout": state.get("timestamp_timeout"),
                "source": "stale_state_file",
                "state_file_enabled": bool(state.get("enabled", True)),
            }
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
