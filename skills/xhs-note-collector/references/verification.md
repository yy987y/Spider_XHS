# 验收与排查

## 基础验收

```bash
PYTHONPATH=. pytest -q
python skills/xhs-note-collector/scripts/bootstrap.py
python skills/xhs-note-collector/scripts/run_collection.py --help
python skills/xhs-note-collector/scripts/launch_wizard.py --help
python /Users/yanchao03/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/xhs-note-collector
```

`bootstrap.py` 默认检查 skill 内置 `runtime/`，会检查 Python 3.10+、Python 依赖、Node.js 20+、npm 依赖和 Chrome/Chromium。Windows 上优先用 `winget --silent` 补装系统软件；macOS 上优先用 Homebrew 补装；Linux 上优先用系统包管理器非交互补装。如果设备连 Python 都没有，先由 `bootstrap_windows.ps1` 或 `bootstrap_unix.sh` 冷启动。

## Windows 冷启动验收

Windows 非技术用户设备可能没有 Python/Node，发布前至少做脚本文本验收：

```bash
rg -n "Python.Python.3.12|OpenJS.NodeJS.LTS|Google.Chrome|--silent|launch_wizard.py" skills/xhs-note-collector/scripts/bootstrap_windows.ps1
```

在真实 Windows 设备上验收时，Agent 内部运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills/xhs-note-collector/scripts/bootstrap_windows.ps1 `
  -SearchQuery "光子嫩肤 北京八大处" `
  -Keywords "光子嫩肤,北京八大处" `
  -DateRange recent_7_days `
  -MaxSearchCandidates 50 `
  -NoOpen
```

首次运行应能用 winget 静默安装 Python 3.12、Node.js LTS、Chrome；若 winget 不可用、企业策略拦截安装或需要管理员确认，Agent 应向交付方报告，不让非技术用户处理终端。

## macOS/Linux 冷启动验收

发布前至少做脚本文本验收：

```bash
rg -n "python@3.12|brew install|apt-get install|dnf install|yum install|pacman -Sy|launch_wizard.py" skills/xhs-note-collector/scripts/bootstrap_unix.sh
```

在真实 macOS/Linux 设备上验收时，Agent 内部运行：

```bash
bash skills/xhs-note-collector/scripts/bootstrap_unix.sh \
  --search-query "光子嫩肤 北京八大处" \
  --keywords "光子嫩肤,北京八大处" \
  --date-range recent_7_days \
  --max-search-candidates 50 \
  --no-open
```

首次运行应能先补齐 Python，再由 `bootstrap.py` 补齐 Python 包、Node.js/npm、Chrome/Chromium 和 npm 包。若无网络、Homebrew 或系统包管理器不可用、sudo 无免密权限、企业策略或安全软件拦截，Agent 应向交付方报告明确原因，不让非技术用户处理终端。

## 分发包验收

只发送 `xhs-note-collector/` 文件夹给非技术用户，所以发布前必须确认它是自包含的：

```bash
find skills/xhs-note-collector/runtime -maxdepth 2 -type f | sort
find skills/xhs-note-collector/runtime -type d \( -name datas -o -name node_modules -o -name __pycache__ \) -prune -print
python skills/xhs-note-collector/scripts/bootstrap.py
```

第一条应包含 `runtime/apis/`、`runtime/spider/`、`runtime/xhs_utils/`、`runtime/static/`、`runtime/requirements.txt`、`runtime/package.json`、`runtime/package-lock.json`。第二条应无输出，避免把个人缓存、历史结果或已安装依赖打入用户包。

## 网页向导 smoke

不触发真实登录时，至少验证本地服务能启动并返回页面：

```bash
python skills/xhs-note-collector/scripts/launch_wizard.py --no-open --port 8765
```

打开 `http://127.0.0.1:8765/` 应看到“小红书笔记采集向导”。验证后用 `Ctrl+C` 停止。

验证自动预填和自动流程参数：

```bash
python skills/xhs-note-collector/scripts/launch_wizard.py \
  --no-open \
  --port 8766 \
  --search-query "光子嫩肤 北京八大处" \
  --date-range recent_7_days \
  --auto-start
```

访问 `/api/status` 应看到 `defaults.auto_start=true`、搜索词已预填、关键词已从搜索词拆分。

## 小批量试跑

```bash
python skills/xhs-note-collector/scripts/run_collection.py \
  --task-name smoke \
  --search-query "大超炮 北京" \
  --keywords "大超炮,北京" \
  --date-range recent_7_days \
  --max-search-candidates 20 \
  --enrich-details
```

真实试跑会打开 skill 专用 Chrome profile。用户需要在弹出的浏览器中完成小红书登录；如果出现登录墙或频控，停止并记录 details summary，不要改用 curl。

默认不要追加 `--use-note-detail-api`。这个开关只允许开发者为了复现旧链路问题临时使用。

## 必查日志事件

- `search_candidate_cap_reached`：公开搜索达到候选上限，标记可能未抓全。
- `search_item_missing_list_card`：公开搜索条目缺少可用列表信息；默认跳过，避免触发详情接口频控。
- `user_channel_disabled_without_detail_api`：指定用户通道依赖详情接口；默认禁用，避免触发频控。
- `api_error`：接口失败或 Cookie 失效。
- `search_no_more`：公开搜索没有更多结果。
- details summary 中 `failed > 0`：部分笔记详情未补全，需要查看 details JSONL 中的 `error`。
