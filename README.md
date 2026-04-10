# macOS Uninstall Cleanup

This skill audits macOS app removals and clears leftover files.
It also tries to keep administrator authentication to a minimum.
It is packaged as a plain skill directory.
It works in both Codex and Claude Code.

## What It Does

- scans common uninstall residue locations without `sudo`
- classifies leftovers by delete strategy before removal
- separates user-space deletes from one batched privileged cleanup
- detects container-managed paths
- detects iCloud-backed paths that should not be retried blindly
- opens the macOS administrator dialog for the final privileged cleanup batch
- includes helper scripts for root-batch cleanup and optional sudo cache tuning

## Repository Layout

- `SKILL.md`: skill instructions and operating workflow
- `agents/openai.yaml`: skill metadata
- `scripts/scan_residue.py`: residue scanner with delete-plan hints
- `scripts/root_cleanup_batch.py`: single-invocation privileged cleanup helper
- `scripts/root_cleanup_prompt.py`: AppleScript wrapper.
  It opens the macOS administrator dialog for the privileged batch.
- `scripts/install_sudo_cache_mode.sh`: optional sudo timestamp policy installer
- `scripts/remove_sudo_cache_mode.sh`: rollback helper
- `scripts/sudo_cache_status.py`: local sudo cache mode status helper
- `tests/test_root_cleanup_prompt.py`: unit tests
  for the administrator-dialog wrapper

## Usage

Run the scanner:

```bash
python3 scripts/scan_residue.py "App Name" Vendor
```

Run a dry-run privileged batch:

```bash
python3 scripts/root_cleanup_batch.py --dry-run \
  --bootout-system /Library/LaunchDaemons/com.vendor.helper.plist \
  --disable-system com.vendor.helper \
  --remove "/Library/Application Support/Vendor"
```

Run the real privileged batch through the macOS administrator dialog:

```bash
python3 scripts/root_cleanup_prompt.py \
  --bootout-system /Library/LaunchDaemons/com.vendor.helper.plist \
  --disable-system com.vendor.helper \
  --remove "/Library/Application Support/Vendor"
```

Important:

- `scripts/root_cleanup_prompt.py`
  uses `osascript ... with administrator privileges`
- it must run in a local macOS GUI session
- the system needs to be able to show an authentication dialog
- it is not suitable for SSH-only shells
- it is not suitable for CI runners or other headless environments
- in headless workflows, use `scripts/root_cleanup_batch.py` instead
- run that helper under an explicit root context

If you still want cross-PTY `sudo` caching for other workflows,
you can install the optional cache mode:

```bash
sudo bash scripts/install_sudo_cache_mode.sh --balanced
```

## Install In Codex

Official Codex docs place user-scoped skills
under `~/.agents/skills/<skill-name>`.
Invoke the skill explicitly with `$skill-name`.

Fastest path:

```bash
git clone https://github.com/yongyaoduan/macos-uninstall-cleanup.git
cd macos-uninstall-cleanup
./install.sh codex
```

Then invoke it in Codex with:

```text
Use $macos-uninstall-cleanup to uninstall a macOS app.
Remove leftover login items, launchd jobs, data, and logs.
```

Notes:

- the installer prefers `~/.agents/skills`
- it falls back to `~/.codex/skills` when that legacy directory already exists
- `./install.sh codex --copy` installs a standalone copy instead of a symlink

## Install In Claude Code

Claude Code docs place personal skills
under `~/.claude/skills/<skill-name>/SKILL.md`.
Invoke the skill with `/skill-name`.

Fastest path:

```bash
git clone https://github.com/yongyaoduan/macos-uninstall-cleanup.git
cd macos-uninstall-cleanup
./install.sh claude
```

Then invoke it in Claude Code with:

```text
/macos-uninstall-cleanup uninstall OneDrive and clean leftover launch agents
```

Notes:

- `./install.sh claude` defaults to a copy install
- use `./install.sh claude --symlink` for a live link to this repo
- choose that mode when you want local edits
- to show up in Claude Code immediately

## Distribution Notes

- Codex supports direct skill folders.
- OpenAI recommends packaging reusable public distributions as plugins.
- That is the better fit when you want reuse beyond local setup.
- Claude Code uses the same `SKILL.md`-based skill format.
- Claude Code also supports project-local skills under `.claude/skills/`.
