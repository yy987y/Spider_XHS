---
name: xhs-note-collector
description: "Use when the user wants a non-technical Xiaohongshu/XHS note collection workflow, keyword note search, recent-day note collection, CDP note content export, Markdown details, XLSX exports, HTML dashboards, interaction metric sorting, or prior Spider_XHS output inspection."
---

# 小红书关键词笔记采集

## 工作流

1. 默认使用 skill 自带的 `runtime/` 运行时；真实分发场景只需要打包发送整个 `xhs-note-collector` 文件夹，不要求用户另行下载完整 `Spider_XHS` 仓库。
2. 用户说出“近 n 天、关键词 xxx”后，Agent 直接启动网页向导并自动打开浏览器；不要把命令行、双击入口、Cookie、脚本路径作为用户主流程。
3. 启动网页向导前，Agent 先执行内部环境自检：缺 Python 的 Windows 走 `scripts/bootstrap_windows.ps1`，缺 Python 的 macOS/Linux 走 `scripts/bootstrap_unix.sh`；Python 可用后统一由 `bootstrap.py` 自动补齐 Python 包、Node.js/npm、Chrome/Chromium 和 npm 包。
4. 启动网页向导时把搜索词、时间范围、关键词和候选上限作为参数传入；默认最多检查 50 条搜索候选。页面打开后会自动检查登录态，没有 Cookie 时自动展示二维码。
5. 用户只需要在浏览器里扫码登录；登录成功后工具自动保存 Cookie、自动开始采集、自动打开受控 Chrome/CDP 补全正文。
6. 一轮任务只处理一组完整搜索词和一组看板关键词。
7. 列表候选走关键词公开搜索；命中的笔记用 Chrome CDP 补全正文、图片和评论。
8. 默认不要启用帖子详情 API。该接口测试中出现过频控，只保留给开发者临时排查，非技术用户分发包主流程不使用。
9. 运行后汇报 Excel、HTML、列表 JSONL、logs JSONL、Markdown 正文目录、详情 JSONL、详情 summary 路径，并说明是否出现候选上限、列表条目跳过、详情失败或可能未抓全。

## Agent 默认启动方式

当用户已经给出搜索需求时，Agent 直接启动浏览器向导。Windows 新设备优先使用 PowerShell 冷启动入口：

```powershell
powershell -ExecutionPolicy Bypass -File skills/xhs-note-collector/scripts/bootstrap_windows.ps1 `
  -SearchQuery "光子嫩肤 北京八大处" `
  -Keywords "光子嫩肤,北京八大处" `
  -DateRange recent_7_days `
  -MaxSearchCandidates 50
```

macOS/Linux 新设备优先使用 shell 冷启动入口：

```bash
bash skills/xhs-note-collector/scripts/bootstrap_unix.sh \
  --search-query "光子嫩肤 北京八大处" \
  --keywords "光子嫩肤,北京八大处" \
  --date-range recent_7_days \
  --max-search-candidates 50
```

如果 Agent 已确认 Python 可用，也可以直接启动 Python 向导。不要传 `--repo`，让脚本自动使用 skill 内置 runtime：

```bash
python skills/xhs-note-collector/scripts/launch_wizard.py \
  --search-query "光子嫩肤 北京八大处" \
  --keywords "光子嫩肤,北京八大处" \
  --date-range recent_7_days \
  --max-search-candidates 50 \
  --auto-start
```

该命令是 Agent 内部执行细节，不要要求非技术用户自己运行、双击脚本或处理终端。浏览器弹出后，用户只需要扫码登录并等待完成。

## 环境自检边界

- Windows、macOS、Linux 都默认由 Agent 内部做系统级软件检测和尽力静默安装；这不是用户操作步骤。
- Windows 冷启动入口是 `scripts/bootstrap_windows.ps1`，会通过 `winget --silent` 静默安装 `Python.Python.3.12`、`OpenJS.NodeJS.LTS`、`Google.Chrome`，并刷新当前进程 PATH 后继续启动网页向导。
- macOS/Linux 冷启动入口是 `scripts/bootstrap_unix.sh`，会先尝试安装 Python，再进入 Python 向导；`bootstrap.py` 会继续尝试补装 Node.js/npm 和 Chrome/Chromium。macOS 优先用 Homebrew 静默安装，Homebrew 缺失时会用官方非交互安装脚本；Linux 优先用系统包管理器的非交互安装参数。
- `bootstrap.py` 会按平台补装缺失或过旧的 Node.js 和 Chrome/Chromium；如果当前 Python 版本过低，会尝试安装 Python 3.12 或系统 Python 3，并要求 Agent 重新启动进程。
- Python 包依赖从 `requirements.txt` 自动安装；Node 包依赖在缺少 `node_modules` 时自动执行 `npm install`。
- Google Chrome/Chromium 会优先从系统 PATH 查找，再检查 macOS `/Applications`、Windows `Program Files`、`Program Files (x86)`、`LOCALAPPDATA`、Linux 常见安装路径。
- 自动安装失败时，Agent 只向交付方报告结构化原因，例如无网络、`winget`/Homebrew/系统包管理器不可用、企业策略拦截、sudo 无免密权限、杀软拦截或安装后 PATH 未刷新；不要把终端报错交给非技术用户。

如果用户没有给出搜索词，只启动空白向导：

```bash
python skills/xhs-note-collector/scripts/launch_wizard.py
```

## 分发包内容

真实给非技术用户分发时，发送整个 `xhs-note-collector/` 文件夹即可。这个文件夹必须包含：

- `SKILL.md`、`agents/`、`references/`、`scripts/`
- `runtime/apis/`：扫码登录和小红书 PC 接口
- `runtime/spider/`：关键词采集、时间过滤、报表、HTML 看板、CDP 详情导出
- `runtime/xhs_utils/`：签名、Cookie、数据解析、HTTP 工具
- `runtime/static/`：小红书签名 JS
- `runtime/requirements.txt`、`runtime/package.json`、`runtime/package-lock.json`

不要把 `datas/`、`node_modules/`、`__pycache__/`、`.env`、历史采集输出、Chrome profile 缓存、测试目录打进用户分发包。首次运行时依赖会在用户设备上由 Agent 内部自检补齐。

## 用户可见话术

告诉用户即可：

> 我会自动打开一个浏览器页面。如果页面显示二维码，请用小红书 App 扫码确认登录；登录后会自动开始采集，完成后我会把 HTML 看板、Excel 和正文目录发给你。

不要让用户复制 Cookie、打开开发者工具、进入终端、手动执行脚本，除非用户明确要排查环境问题。

开发者如需临时验证外部完整仓库，可在 Agent 环境中设置 `XHS_NOTE_COLLECTOR_REPO=/path/to/Spider_XHS` 后再启动；不要把这个调试方式交给普通用户。

## 命令行备用方式

仅用于开发者排查，不作为普通用户流程：

```bash
python skills/xhs-note-collector/scripts/run_collection.py \
  --task-name 大超炮北京 \
  --search-query "大超炮 北京" \
  --keywords "大超炮,北京" \
  --date-range recent_7_days \
  --max-search-candidates 50 \
  --enrich-details
```

## 何时读取 references

- 需要字段、sheet、JSONL 结构时，读取 `references/input-output.md`。
- 需要验收、smoke run 或排查失败时，读取 `references/verification.md`。
