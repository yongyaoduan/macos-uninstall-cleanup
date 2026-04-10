# macOS Uninstall Cleanup

这个技能用来检查 macOS 应用是否卸干净、清掉残留文件，并尽量把管理员认证压缩到一次。它是普通技能目录，Codex 和 Claude Code 都能直接用。

## What It Does

- scans common uninstall residue locations without `sudo`
- classifies leftovers by delete strategy before removal
- separates user-space deletes from one batched privileged cleanup
- detects container-managed and iCloud-backed paths that should not be retried blindly
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
- `tests/test_root_cleanup_prompt.py`: unit tests for the administrator-dialog wrapper

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

如果你在别的流程里仍然需要跨 PTY 共享 `sudo` 缓存，可以再装这个可选模式：

```bash
sudo bash scripts/install_sudo_cache_mode.sh --balanced
```

## Install In Codex

Official Codex docs place user-scoped skills under `~/.agents/skills/<skill-name>`.
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
- it falls back to `~/.codex/skills` when that legacy directory already exists on the machine
- `./install.sh codex --copy` installs a standalone copy instead of a symlink

## Install In Claude Code

Claude Code docs place personal skills under `~/.claude/skills/<skill-name>/SKILL.md`.
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
- use `./install.sh claude --symlink` if you want edits in this repo to reflect directly in Claude Code

## Distribution Notes

- Codex supports direct skill folders.
- OpenAI recommends packaging reusable public distributions as plugins when you want broader reuse beyond local setup.
- Claude Code uses the same `SKILL.md`-based skill format.
- Claude Code also supports project-local skills under `.claude/skills/`.
