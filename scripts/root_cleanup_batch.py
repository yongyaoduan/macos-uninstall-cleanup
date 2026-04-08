#!/usr/bin/env python3
import argparse
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path


def invoking_home() -> Path:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    return Path.home()


ALLOWED_ROOTS = (
    Path("/Applications"),
    Path("/Library"),
    Path("/Users/Shared"),
    Path("/private/var/db/receipts"),
)

ALLOWED_BOOTOUT_ROOTS = (
    Path("/Library/LaunchDaemons"),
)


def top_level_container_candidate(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return len(relative.parts) == 1


def allowed_user_roots():
    home = invoking_home()
    return (
        home / "Library/Containers",
        home / "Library/Group Containers",
        home / "Library/Mobile Documents",
    )


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_remove_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        raise ValueError(f"remove path must be absolute: {raw_path}")

    for root in ALLOWED_ROOTS:
        if path != root and is_relative_to(path, root):
            return path

    for root in allowed_user_roots():
        if path == root:
            continue
        if is_relative_to(path, root):
            if not top_level_container_candidate(path, root):
                raise ValueError(
                    "user Library container and iCloud removals must target a top-level app container directory, not nested content"
                )
            if root.name == "Mobile Documents" and path.name == "com~apple~CloudDocs":
                raise ValueError(
                    "refusing to remove the top-level iCloud Drive container com~apple~CloudDocs"
                )
            return path

    raise ValueError(f"remove path is outside approved uninstall roots: {raw_path}")


def validate_bootout_system_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        raise ValueError(f"bootout plist must be absolute: {raw_path}")

    if path != Path("/Library/LaunchAgents") and is_relative_to(path, Path("/Library/LaunchAgents")):
        raise ValueError(
            "bootout system only supports /Library/LaunchDaemons; unload /Library/LaunchAgents from the target gui domain before the root batch"
        )

    for root in ALLOWED_BOOTOUT_ROOTS:
        if path != root and is_relative_to(path, root):
            return path

    raise ValueError(f"bootout plist is outside approved launchd roots: {raw_path}")


def normalize_system_label(label: str) -> str:
    label = label.strip()
    if not label:
        raise ValueError("system label cannot be empty")
    if label.startswith("system/"):
        return label
    return f"system/{label}"


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    entry = {
        "cmd": cmd,
        "returncode": result.returncode,
    }
    if result.stdout.strip():
        entry["stdout"] = result.stdout.strip()
    if result.stderr.strip():
        entry["stderr"] = result.stderr.strip()
    return entry


def main():
    parser = argparse.ArgumentParser(
        description="Execute privileged macOS uninstall actions in one batch."
    )
    parser.add_argument("--bootout-system", action="append", default=[], metavar="PLIST")
    parser.add_argument("--disable-system", action="append", default=[], metavar="LABEL")
    parser.add_argument("--remove", action="append", default=[], metavar="PATH")
    parser.add_argument("--forget-pkg", action="append", default=[], metavar="PKGID")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        bootout_paths = [str(validate_bootout_system_path(path)) for path in args.bootout_system]
        remove_paths = [str(validate_remove_path(path)) for path in args.remove]
        disable_labels = [normalize_system_label(label) for label in args.disable_system]
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)

    plan = {
        "bootout_system": bootout_paths,
        "disable_system": disable_labels,
        "remove": remove_paths,
        "forget_pkg": [pkg for pkg in args.forget_pkg if pkg.strip()],
        "invoking_user": os.environ.get("SUDO_USER") or os.environ.get("USER") or "unknown",
        "invoking_home": str(invoking_home()),
    }

    if args.dry_run:
        print(json.dumps({"dry_run": True, "plan": plan}, ensure_ascii=False, indent=2))
        return

    if os.geteuid() != 0:
        print(
            json.dumps(
                {
                    "error": "Run this helper under sudo so all privileged work happens in one prompt.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    executed = []
    for plist in plan["bootout_system"]:
        executed.append(run(["launchctl", "bootout", "system", plist]))
    for label in plan["disable_system"]:
        executed.append(run(["launchctl", "disable", label]))
    for path in plan["remove"]:
        executed.append(run(["rm", "-rf", path]))
    for pkg in plan["forget_pkg"]:
        executed.append(run(["pkgutil", "--forget", pkg]))

    failures = [entry for entry in executed if entry["returncode"] != 0]
    print(
        json.dumps(
            {
                "plan": plan,
                "executed": executed,
                "failures": failures,
                "ok": not failures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
