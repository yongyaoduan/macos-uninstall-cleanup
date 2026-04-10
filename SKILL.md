---
name: macos-uninstall-cleanup
description: Use when uninstalling a macOS app or cleaning leftover app files and startup hooks after uninstall.
---

# macOS Uninstall Cleanup

## Overview

Use this skill to check whether a macOS app was fully removed, delete confirmed residue, and make sure startup hooks are gone.

Work in three passes: inventory first, delete second, verify last.

## Password Minimization

Rules:

- Do not use `sudo` for the initial scan unless a specific read operation is blocked.
- Prefer plain `find`, `launchctl print-disabled system`, `osascript`, and receipt scans first.
- Do not use `sfltool` unless the user explicitly asks for it.
- Before marking a path `root_required`, check whether its delete parent is actually writable by the current user. `/Applications` and `/Users/Shared` are not automatically root-only on every machine.
- After `python3 scripts/scan_residue.py ...`, use `cleanup_plan.user_delete_paths` for non-root deletes.
- Then combine `cleanup_plan.root_batch_remove_paths` into one privileged action.
- If `cleanup_plan.root_batch_remove_paths` is empty, do not prompt for administrator authentication.
- When privileged work is needed, prefer one `python3 scripts/root_cleanup_prompt.py ...` invocation. Let that single prompt handle unloads, disables, deletes, and receipt forgets.
- `scripts/root_cleanup_prompt.py` requires a local macOS GUI session because it relies on an AppleScript administrator dialog. Do not recommend it for SSH-only, CI, or other headless shells.
- In headless environments, the prompt wrapper is the wrong tool. Tell the user to run `scripts/root_cleanup_batch.py` from an explicit root context instead.
- Never output more than one independent privileged command for uninstall work in the same answer. Gather every root-only action first, then emit one helper invocation.
- Validate privileged plans with `python3 scripts/root_cleanup_batch.py --dry-run ...` before prompting.
- Do not use `sudo` for verification, reporting, or receipt listing.
- If a path is under `~/Library/Containers`, `~/Library/Group Containers`, or `~/Library/Mobile Documents`, classify it before deleting.
- If macOS blocks the delete, stop and report why instead of retrying blindly.

## Quick Start

Run the bundled scanner with product and vendor names:

```bash
python3 scripts/scan_residue.py "Battle.net" Blizzard
python3 scripts/scan_residue.py Riot "League of Legends" LeagueClient RiotClient
python3 scripts/scan_residue.py Grammarly
```

The scanner inventories:

- app bundles and broken links under `/Applications` and `~/Applications`
- user and system leftovers under `~/Library`, `/Library`, and `/Users/Shared`
- `launchctl` labels, running processes, and login items
- delete constraints such as `root_required`, `container_managed`, `may_need_full_disk_access`, and `icloud_synced`
- the delete strategy for each matched path
- a `cleanup_plan` that separates user deletes from the privileged batch

## Workflow

### 1. Inventory Before Deleting

Start with a read-only pass.

Useful commands:

```bash
python3 scripts/scan_residue.py "App Name" Vendor
du -sh "/Users/Shared/Vendor" "$HOME/Library/Application Support/App Name" 2>/dev/null
pkgutil --pkgs | rg -i 'vendor|app'
```

Login items and launchctl:

```bash
osascript -e 'tell application "System Events" to get the properties of every login item'
launchctl list | rg -i 'vendor|app'
```

If `cleanup_plan.root_batch_remove_paths` is empty, do not escalate.

If the scanner flags a path as `container_managed`, `may_need_full_disk_access`, or `icloud_synced`, treat that as preflight feedback and adjust the plan before deleting anything.

### 2. Separate Scope

Before deleting, classify findings into these buckets:

- app bundle or broken `/Applications/*.app` link
- user data under `~/Library`
- system helpers and launchd files under `/Library`
- shared vendor data under `/Users/Shared`
- iCloud containers under `~/Library/Mobile Documents`
- protected container metadata, where macOS may block `rm` even for root without the right privacy context

Shared vendor folders may belong to multiple products.

Protected-path notes:

- `~/Library/Containers/*` and some `~/Library/Group Containers/*` items may be container-managed
- `~/Library/Mobile Documents/*` may reappear from iCloud
- if Full Disk Access is missing, stop and report that once instead of retrying deletes

### 2a. Preferred Example Flow

Use one combined privileged plan, not several small privileged commands.

Example flow:

```bash
python3 scripts/scan_residue.py "App Name" Vendor

uid=$(id -u)
launchctl bootout gui/$uid "$HOME/Library/LaunchAgents/com.vendor.agent.plist" 2>/dev/null || true
launchctl disable gui/$uid/com.vendor.agent 2>/dev/null || true
osascript -e 'tell application "System Events" to delete login item "App Name"' 2>/dev/null || true
rm -rf "$HOME/Library/Application Support/App Name"
rm -f "$HOME/Library/Preferences/com.vendor.app.plist"

python3 scripts/root_cleanup_batch.py --dry-run \
  --bootout-system /Library/LaunchDaemons/com.vendor.helper.plist \
  --disable-system com.vendor.helper \
  --remove "/Applications/App Name.app" \
  --remove /Library/LaunchDaemons/com.vendor.helper.plist \
  --remove /Library/PrivilegedHelperTools/com.vendor.helper \
  --remove "/Library/Application Support/Vendor" \
  --remove "/Users/Shared/App Name" \
  --forget-pkg com.vendor.package

python3 scripts/root_cleanup_prompt.py \
  --bootout-system /Library/LaunchDaemons/com.vendor.helper.plist \
  --disable-system com.vendor.helper \
  --remove "/Applications/App Name.app" \
  --remove /Library/LaunchDaemons/com.vendor.helper.plist \
  --remove /Library/PrivilegedHelperTools/com.vendor.helper \
  --remove "/Library/Application Support/Vendor" \
  --remove "/Users/Shared/App Name" \
  --forget-pkg com.vendor.package

python3 scripts/scan_residue.py "App Name" Vendor
```

Do not split the root-only part above into separate privileged prompts unless the helper script truly cannot express the required operation.

### 3. Disable Startup Hooks First

Do not delete active launch files before unloading them.

User domain:

```bash
uid=$(id -u)
launchctl bootout gui/$uid /path/to/agent.plist 2>/dev/null || true
launchctl disable gui/$uid/com.vendor.agent 2>/dev/null || true
```

System domain:

```bash
# Add these flags to the single root helper invocation from section 2a:
--bootout-system /Library/LaunchDaemons/com.vendor.helper.plist
--disable-system com.vendor.helper
```

`--bootout-system` is only for `/Library/LaunchDaemons`. Do not pass `/Library/LaunchAgents/*` to it.

For login items:

```bash
osascript -e 'tell application "System Events" to delete login item "App Name"'
```

Keep multiple system items in the same helper invocation.

### 4. Remove Approved Residue

Delete only after the scope is confirmed.

Typical user paths:

```bash
rm -rf "$HOME/Library/Application Support/App Name"
rm -rf "$HOME/Library/Caches/com.vendor.app"
rm -rf "$HOME/Library/Logs/App Name"
rm -f "$HOME/Library/Preferences/com.vendor.app.plist"
rm -rf "$HOME/Library/Saved Application State/com.vendor.app.savedState"
```

Typical system paths:

```bash
# Add these flags to the single root helper invocation from section 2a:
--remove /Library/LaunchAgents/com.vendor.agent.plist
--remove /Library/LaunchDaemons/com.vendor.helper.plist
--remove /Library/PrivilegedHelperTools/com.vendor.helper
--remove "/Library/Application Support/Vendor"
```

Typical shared paths:

```bash
# Add these flags to the single root helper invocation from section 2a:
--remove "/Users/Shared/App Name"
--remove "/Users/Shared/Vendor"
```

If `/Applications/App Name.app` is a symlink whose target is gone, remove the link:

```bash
# Add this flag to the single root helper invocation from section 2a:
--remove "/Applications/App Name.app"
```

If package receipts remain and the user wants a deeper cleanup:

```bash
pkgutil --pkgs | rg -i 'vendor|app'
# Add this flag to the single root helper invocation from section 2a:
--forget-pkg com.vendor.package
```

Do not blindly retry protected deletes. Preferred handling:

- `container_managed`: report that Full Disk Access or a manual Finder cleanup may be required
- `icloud_synced`: delete locally once, then remove the same container from Finder iCloud Drive or [iCloud.com](https://www.icloud.com/) if it reappears
- `root_required`: batch all matching paths into one helper invocation, not several separate privileged prompts

### 5. Verify Cleanup

Repeat the same scan after deletion.

Minimum verification:

```bash
python3 scripts/scan_residue.py "App Name" Vendor
launchctl list | rg -i 'vendor|app'
ps aux | rg -i 'vendor|app'
```

Interpret results carefully:

- no matching files plus no matching `launchctl` labels is the strongest signal that cleanup succeeded
- if a file path still exists, the uninstall is not complete

## Special Cases

### iCloud Containers

App-specific iCloud containers under `~/Library/Mobile Documents` may require administrator authentication to remove. Some empty containers can reappear if iCloud sync restores them.

If a container keeps returning:

1. add the local delete path to the same root helper invocation
2. check Finder iCloud Drive or [iCloud.com](https://www.icloud.com/) for the same container
3. remove it from the cloud source as well

If a container delete fails with `Operation not permitted`, do not keep looping on the same command. Report that the remaining item is protected by macOS privacy or container controls and switch to a manual or Full Disk Access path.

### Shared Vendor Data

Do not assume every vendor folder is safe to wipe. Audit contents first when the vendor may own multiple apps or games.

## Reporting Back

When you finish, summarize:

- what was still installed
- what residue you removed
- what startup items were disabled or deleted
- which items were skipped because of container or iCloud protection
- what, if anything, remains and why

Keep the summary concrete. Prefer exact paths over generic statements.
