# macOS Uninstall Cleanup

A Codex skill for auditing macOS app removals, cleaning leftover files, and minimizing repeated admin prompts during uninstall work.

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

## Install As A Local Codex Skill

Copy or clone this directory into:

```bash
$CODEX_HOME/skills/macos-uninstall-cleanup
```

Then invoke it in Codex with:

```text
Use $macos-uninstall-cleanup to uninstall a macOS app and remove leftover login items, launchd jobs, data, and logs.
```
