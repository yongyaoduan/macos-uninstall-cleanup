# macOS Uninstall Cleanup

An agent skill for auditing macOS app removals, cleaning leftover files, and minimizing repeated admin prompts during uninstall work. It is packaged as a plain skill directory so it can be used in both Codex and Claude Code.

## What It Does

- scans common uninstall residue locations without `sudo`
- classifies leftovers by delete strategy before removal
- separates user-space deletes from one batched privileged cleanup
- detects container-managed and iCloud-backed paths that should not be retried blindly
- includes helper scripts for root-batch cleanup and optional sudo cache tuning

## Repository Layout

- `SKILL.md`: skill instructions and operating workflow
- `agents/openai.yaml`: skill metadata
- `scripts/scan_residue.py`: residue scanner with delete-plan hints
- `scripts/root_cleanup_batch.py`: single-invocation privileged cleanup helper
- `scripts/install_sudo_cache_mode.sh`: optional sudo timestamp policy installer
- `scripts/remove_sudo_cache_mode.sh`: rollback helper
- `scripts/sudo_cache_status.py`: local sudo cache mode status helper

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

Install the optional cross-PTY sudo cache mode:

```bash
sudo bash scripts/install_sudo_cache_mode.sh --balanced
```

## Install In Codex

Official Codex docs say user-scoped skills live under `~/.agents/skills/<skill-name>` and can be invoked explicitly with `$skill-name`.

Fastest path:

```bash
git clone https://github.com/yongyaoduan/macos-uninstall-cleanup.git
cd macos-uninstall-cleanup
./install.sh codex
```

Then invoke it in Codex with:

```text
Use $macos-uninstall-cleanup to uninstall a macOS app and remove leftover login items, launchd jobs, data, and logs.
```

Notes:

- the installer prefers `~/.agents/skills`, but falls back to `~/.codex/skills` when that legacy directory already exists on the machine
- `./install.sh codex --copy` installs a standalone copy instead of a symlink

## Install In Claude Code

Claude Code docs say personal skills live under `~/.claude/skills/<skill-name>/SKILL.md` and can be invoked with `/skill-name`.

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
- use `./install.sh claude --symlink` if you want edits in this repo to reflect directly in Claude Code

## Distribution Notes

- Codex supports direct skill folders, but OpenAI recommends packaging reusable public distributions as plugins when you want broader reuse beyond local setup.
- Claude Code uses the same `SKILL.md`-based skill format and also supports project-local skills under `.claude/skills/`.
