#!/usr/bin/env python3
import json
import os
import pwd
from pathlib import Path


def target_user():
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "unknown"


def target_home(user: str) -> Path:
    try:
        return Path(pwd.getpwnam(user).pw_dir)
    except KeyError:
        return Path.home()


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

    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except (OSError, json.JSONDecodeError):
            state = None
        if isinstance(state, dict):
            result.update(
                {
                    "enabled": bool(state.get("enabled", True)),
                    "mode": state.get("mode"),
                    "timestamp_timeout": state.get("timestamp_timeout"),
                    "source": "state_file",
                }
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

    if dropin.exists():
        result.update(
            {
                "enabled": True,
                "source": "dropin_name",
            }
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
