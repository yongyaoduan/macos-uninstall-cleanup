---
name: macos-uninstall-cleanup
description: Use when uninstalling a macOS app or cleaning leftover app files and startup hooks after uninstall.
---

# macOS Uninstall Cleanup

## Overview

这个技能用于检查 macOS 应用卸载是否完整，删除已经确认的残留，并确认启动项已经消失。

流程很简单：先盘点，再删除，再复查。

## Password Minimization

Rules:

- 初次扫描不要用 `sudo`，除非某个只读检查真的被权限挡住。
- 先用普通命令做盘点：`find`、`launchctl print-disabled system`、`osascript`、`pkgutil`。
- 除非用户明确要求，否则不要用 `sfltool`。
- 把路径标成 `root_required` 之前，先看父目录是不是当前用户真有删除权限。`/Applications` 和 `/Users/Shared` 不一定都需要提权。
- 跑完 `python3 scripts/scan_residue.py ...` 后，先用 `cleanup_plan.user_delete_paths` 处理非提权删除。
- 再把 `cleanup_plan.root_batch_remove_paths` 汇总成一次提权操作。
- 如果 `cleanup_plan.root_batch_remove_paths` 为空，就不要再弹管理员认证框。
- 需要提权时，优先用一条 `python3 scripts/root_cleanup_prompt.py ...`。让这一次系统弹窗把卸载、停用、删除和 receipt forget 全做完。
- 同一轮卸载里不要给出多个独立的提权命令。先把 root 侧操作收齐，再发一次。
- 弹窗前先用 `python3 scripts/root_cleanup_batch.py --dry-run ...` 检查计划。
- 复查、汇报、列 receipt 时不要用 `sudo`。
- 遇到 `~/Library/Containers`、`~/Library/Group Containers`、`~/Library/Mobile Documents` 下的路径，先分类型再删。
- macOS 如果拦了，就停下来说明原因，不要硬重试。

## Quick Start

用产品名和厂商名跑自带扫描器：

```bash
python3 scripts/scan_residue.py "Battle.net" Blizzard
python3 scripts/scan_residue.py Riot "League of Legends" LeagueClient RiotClient
python3 scripts/scan_residue.py Grammarly
```

扫描器会列出：

- `/Applications` 和 `~/Applications` 下面的应用包与坏链接
- `~/Library`、`/Library`、`/Users/Shared` 下面的用户级和系统级残留
- `launchctl` 标签、运行中的进程和登录项
- 删除约束，比如 `root_required`、`container_managed`、`may_need_full_disk_access`、`icloud_synced`
- 每个路径对应的删除策略
- 把普通删除和提权删除分开的 `cleanup_plan`

## Workflow

### 1. Inventory Before Deleting

先做只读盘点。

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

如果 `cleanup_plan.root_batch_remove_paths` 为空，就不要提权。

如果扫描器把路径标成 `container_managed`、`may_need_full_disk_access` 或 `icloud_synced`，先调整方案，再决定删不删。

### 2. Separate Scope

删除前，先把发现分到这些桶里：

- app bundle or broken `/Applications/*.app` link
- user data under `~/Library`
- system helpers and launchd files under `/Library`
- shared vendor data under `/Users/Shared`
- iCloud containers under `~/Library/Mobile Documents`
- 受保护的容器元数据。权限上下文不对时，即使是 root，macOS 也可能拦下 `rm`

共享厂商目录可能不只属于一个产品。

受保护路径注意点：

- `~/Library/Containers/*` 和部分 `~/Library/Group Containers/*` 项可能由系统容器管理
- `~/Library/Mobile Documents/*` 可能会被 iCloud 重新拉回本地
- 如果缺 Full Disk Access，就停下来说明一次，不要反复重试删除

### 2a. Preferred Example Flow

提权操作要合并成一批，不要拆成好几条小命令。

推荐流程示例：

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

除非辅助脚本确实表达不了，否则不要把上面的 root 操作拆成多个系统弹窗。

### 3. Disable Startup Hooks First

先卸载启动项，再删文件。

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

多个 system 项目放到同一个 helper 调用里。

### 4. Remove Approved Residue

确认范围后再删。

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

受保护路径不要盲目重试，按下面的方式处理：

- `container_managed`: report that Full Disk Access or a manual Finder cleanup may be required
- `icloud_synced`: 先删本地。如果它又回来，再去 Finder 的 iCloud Drive 或 [iCloud.com](https://www.icloud.com/) 删同一个容器
- `root_required`: 把所有命中路径并到同一个 helper 调用里，不要拆成多个提权弹窗

### 5. Verify Cleanup

删完后再跑同一轮扫描。

Minimum verification:

```bash
python3 scripts/scan_residue.py "App Name" Vendor
launchctl list | rg -i 'vendor|app'
ps aux | rg -i 'vendor|app'
```

复查时按这个标准判断：

- 没有命中文件，也没有匹配到 `launchctl` 标签，基本就说明清理干净了
- 如果某个路径还在，卸载就还没完成

## Special Cases

### iCloud Containers

`~/Library/Mobile Documents` 下面的应用 iCloud 容器，有时需要管理员认证才能删。有些空目录会被 iCloud 同步重新拉回来。

如果容器删了又回来：

1. 把本地删除路径加进同一个 root helper 调用
2. 去 Finder 的 iCloud Drive 或 [iCloud.com](https://www.icloud.com/) 找同一个容器
3. 云端也一起删掉

如果容器删除报 `Operation not permitted`，不要在同一条命令上死循环。直接说明它被 macOS 隐私或容器机制保护了，然后切到 Full Disk Access 或手动清理。

### Shared Vendor Data

不要默认厂商目录都能整包删掉。厂商名下面如果挂着多个应用或游戏，先看内容。

## Reporting Back

完成后按下面几点汇报：

- 还装着什么
- 这次删了哪些残留
- 停掉或删掉了哪些启动项
- 哪些项目因为容器或 iCloud 保护而跳过
- 还剩什么，以及为什么还在

汇报写具体，尽量给出准确路径，不要只说“已经清理”。
