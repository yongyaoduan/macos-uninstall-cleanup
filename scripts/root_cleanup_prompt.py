#!/usr/bin/env python3
import shlex
import subprocess
import sys
from pathlib import Path


def helper_path() -> Path:
    return Path(__file__).with_name("root_cleanup_batch.py")


def build_shell_script(args: list[str]) -> str:
    quoted_parts = [shlex.quote("python3"), shlex.quote(str(helper_path()))]
    quoted_parts.extend(shlex.quote(arg) for arg in args)
    return " ".join(quoted_parts)


def build_osascript_command(args: list[str]) -> list[str]:
    shell_script = build_shell_script(args)
    escaped_shell_script = shell_script.replace("\\", "\\\\").replace('"', '\\"')
    return [
        "osascript",
        "-e",
        f'do shell script "{escaped_shell_script}" with administrator privileges',
    ]


def run_prompt(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_osascript_command(args),
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    result = run_prompt(sys.argv[1:])
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
