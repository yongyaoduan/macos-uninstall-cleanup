#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


HOME = Path.home()

ROOTS = {
    "applications": [
        (Path("/Applications"), 3),
        (HOME / "Applications", 3),
    ],
    "shared": [
        (Path("/Users/Shared"), 4),
    ],
    "user_library": [
        (HOME / "Library/Application Support", 5),
        (HOME / "Library/Caches", 4),
        (HOME / "Library/Preferences", 3),
        (HOME / "Library/Logs", 5),
        (HOME / "Library/Saved Application State", 3),
        (HOME / "Library/HTTPStorages", 3),
        (HOME / "Library/WebKit", 4),
        (HOME / "Library/Containers", 4),
        (HOME / "Library/Group Containers", 4),
        (HOME / "Library/Cookies", 3),
        (HOME / "Library/LaunchAgents", 3),
        (HOME / "Library/Application Support/CrashReporter", 3),
        (HOME / "Library/Mobile Documents", 3),
    ],
    "system_library": [
        (Path("/Library/LaunchAgents"), 3),
        (Path("/Library/LaunchDaemons"), 3),
        (Path("/Library/Application Support"), 5),
        (Path("/Library/Preferences"), 3),
        (Path("/Library/Caches"), 3),
        (Path("/Library/PrivilegedHelperTools"), 3),
        (Path("/Library/Logs/DiagnosticReports"), 3),
        (Path("/Library/Input Methods"), 4),
    ],
    "receipts": [
        (Path("/private/var/db/receipts"), 3),
    ],
}


def escape_find_term(term: str) -> str:
    return (
        term.replace("[", "[[]")
        .replace("]", "[]]")
        .replace("*", "[*]")
        .replace("?", "[?]")
    )


def run(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except FileNotFoundError:
        return ""
    except subprocess.TimeoutExpired:
        return ""
    return result.stdout


def normalized_terms(terms):
    return [t.strip().lower() for t in terms if t.strip()]


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def line_matches(text: str, terms):
    lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in terms):
            lines.append(line)
    return lines


def path_entry(path_str: str):
    path = Path(path_str)
    entry = {
        "path": path_str,
        "kind": "symlink" if path.is_symlink() else ("dir" if path.is_dir() else "file"),
        "broken_symlink": path.is_symlink() and not path.exists(),
    }
    constraints, notes, delete_strategy = classify_path(path)
    if constraints:
        entry["constraints"] = constraints
    if notes:
        entry["notes"] = notes
    entry["delete_strategy"] = delete_strategy
    return entry


def container_managed(path: Path) -> bool:
    if not path.exists():
        return False

    metadata_path = path / ".com.apple.containermanagerd.metadata.plist"
    if metadata_path.exists():
        return True

    try:
        result = subprocess.run(
            ["xattr", "-p", "com.apple.containermanager.identifier", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def deletion_parent(path: Path) -> Path:
    parent = path.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return parent


def delete_requires_root(path: Path) -> bool:
    parent = deletion_parent(path)
    return not os.access(parent, os.W_OK | os.X_OK)


def classify_path(path: Path):
    constraints = []
    notes = []
    delete_strategy = "user_delete"

    if is_relative_to(path, Path("/Applications")):
        if delete_requires_root(path):
            constraints.append("root_required")
            notes.append("This app bundle's parent directory is not writable by the current user.")
            delete_strategy = "root_batch"
        else:
            notes.append("This app bundle is removable by the current user on this machine.")

    if is_relative_to(path, Path("/Users/Shared")) or is_relative_to(path, Path("/private/var/db/receipts")):
        if delete_requires_root(path):
            constraints.append("root_required")
            notes.append("Shared or receipt files should be removed in one privileged batch.")
            delete_strategy = "root_batch"

    if is_relative_to(path, Path("/Library")):
        if delete_requires_root(path):
            constraints.append("root_required")
            notes.append("System library items should be unloaded first, then removed in one privileged batch.")
            delete_strategy = "root_batch"

    if is_relative_to(path, HOME / "Library/Containers") or is_relative_to(path, HOME / "Library/Group Containers"):
        if container_managed(path):
            constraints.extend(["container_managed", "may_need_full_disk_access"])
            notes.append("Managed by macOS container services; rm may fail with Operation not permitted.")
            delete_strategy = "manual_or_full_disk_access"

    if is_relative_to(path, HOME / "Library/Mobile Documents"):
        constraints.append("icloud_synced")
        notes.append("iCloud containers can reappear after local deletion unless removed from the cloud source too.")
        delete_strategy = "icloud_local_and_cloud_delete"

    if path.is_symlink() and not path.exists():
        notes.append("Broken symlink residue is usually safe to remove after verifying the target is gone.")

    constraints = list(dict.fromkeys(constraints))
    notes = list(dict.fromkeys(notes))
    return constraints, notes, delete_strategy


def find_matches(terms):
    root_order = []
    searches = []
    for category, roots in ROOTS.items():
        for root, maxdepth in roots:
            if root.exists():
                root_order.append((str(root), category))
                searches.append((str(root), maxdepth))

    if not searches:
        return {category: [] for category in ROOTS}

    categorized = {category: [] for category in ROOTS}
    seen = set()

    for root, maxdepth in searches:
        cmd = ["find", root, "-maxdepth", str(maxdepth), "("]
        first = True
        for term in terms:
            pattern = f"*{escape_find_term(term)}*"
            if not first:
                cmd.append("-o")
            cmd.extend(["-iname", pattern])
            first = False
        cmd.append(")")

        raw = run(cmd)
        for line in raw.splitlines():
            if not line or line in seen:
                continue
            seen.add(line)
            category = "user_library"
            for root_path, root_category in sorted(root_order, key=lambda item: len(item[0]), reverse=True):
                if line == root_path or line.startswith(root_path + "/"):
                    category = root_category
                    break
            categorized[category].append(path_entry(line))

    for category in categorized:
        categorized[category].sort(key=lambda item: item["path"].lower())
    return categorized


def login_items(terms):
    script = 'tell application "System Events" to get the properties of every login item'
    raw = run(["osascript", "-e", script])
    return line_matches(raw, terms)


def launchctl_loaded(terms):
    raw = run(["launchctl", "list"])
    return line_matches(raw, terms)


def launchctl_disabled(terms, domain):
    if domain == "gui":
        target = f"gui/{os.getuid()}"
    else:
        target = "system"
    raw = run(["launchctl", "print-disabled", target])
    return line_matches(raw, terms)


def btm_matches(terms):
    raw = run(["sfltool", "dumpbtm"])
    return line_matches(raw, terms)


def running_processes(terms):
    raw = run(["ps", "aux"])
    lines = []
    for line in raw.splitlines():
        lowered = line.lower()
        if "scan_residue.py" in lowered:
            continue
        if any(term in lowered for term in terms):
            lines.append(line)
    return lines


def summarize_paths(paths):
    summary = {
        "total_matches": 0,
        "root_batch": 0,
        "manual_or_full_disk_access": 0,
        "icloud_local_and_cloud_delete": 0,
        "user_delete": 0,
        "constraints": {},
    }

    for category_entries in paths.values():
        for entry in category_entries:
            summary["total_matches"] += 1
            strategy = entry.get("delete_strategy", "user_delete")
            summary[strategy] = summary.get(strategy, 0) + 1
            for constraint in entry.get("constraints", []):
                summary["constraints"][constraint] = summary["constraints"].get(constraint, 0) + 1

    return summary


def compact_entries(entries):
    kept = []
    kept_dirs = []
    seen = set()

    for entry in sorted(entries, key=lambda item: (len(item["path"]), item["path"].lower())):
        path_str = entry["path"]
        if path_str in seen:
            continue

        path = Path(path_str)
        if any(is_relative_to(path, parent) for parent in kept_dirs):
            continue

        kept.append(entry)
        seen.add(path_str)
        if entry.get("kind") == "dir":
            kept_dirs.append(path)

    return kept


def build_cleanup_plan(paths):
    grouped = {
        "user_delete": [],
        "root_batch": [],
        "manual_or_full_disk_access": [],
        "icloud_local_and_cloud_delete": [],
    }

    for category_entries in paths.values():
        for entry in category_entries:
            strategy = entry.get("delete_strategy", "user_delete")
            grouped.setdefault(strategy, []).append(entry)

    user_entries = compact_entries(grouped["user_delete"])
    root_entries = compact_entries(grouped["root_batch"])
    manual_entries = compact_entries(grouped["manual_or_full_disk_access"])
    icloud_entries = compact_entries(grouped["icloud_local_and_cloud_delete"])

    return {
        "user_delete_paths": [entry["path"] for entry in user_entries],
        "root_batch_remove_paths": [entry["path"] for entry in root_entries],
        "manual_review_paths": [entry["path"] for entry in manual_entries],
        "icloud_local_delete_paths": [entry["path"] for entry in icloud_entries],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scan common macOS uninstall residue locations for product or vendor names."
    )
    parser.add_argument(
        "--include-btm",
        action="store_true",
        help="Include `sfltool dumpbtm` in runtime checks.",
    )
    parser.add_argument("terms", nargs="+", help="Product or vendor names to search for")
    args = parser.parse_args()

    terms = normalized_terms(args.terms)
    if not terms:
        print(json.dumps({"error": "At least one search term is required"}, ensure_ascii=False))
        sys.exit(1)

    paths = find_matches(terms)
    cleanup_plan = build_cleanup_plan(paths)
    output = {
        "search_terms": args.terms,
        "paths": paths,
        "summary": summarize_paths(paths),
        "cleanup_plan": cleanup_plan,
        "runtime": {
            "login_items": login_items(terms),
            "launchctl_loaded": launchctl_loaded(terms),
            "launchctl_disabled_gui": launchctl_disabled(terms, "gui"),
            "launchctl_disabled_system": launchctl_disabled(terms, "system"),
            "btm_matches": btm_matches(terms) if args.include_btm else [],
            "running_processes": running_processes(terms),
        },
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
