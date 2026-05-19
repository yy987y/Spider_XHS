#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_MAX_SEARCH_CANDIDATES = 50


def _load_bootstrap():
    path = Path(__file__).resolve().with_name("bootstrap.py")
    spec = importlib.util.spec_from_file_location("xhs_note_collector_bootstrap", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load_bootstrap()
REPO_ROOT = BOOTSTRAP.find_repo()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.dont_write_bytecode = True

if not os.getenv("XHS_NOTE_COLLECTOR_SKIP_BOOTSTRAP"):
    BOOTSTRAP.ensure_environment(REPO_ROOT)

try:
    import qrcode  # noqa: E402
except ImportError:  # pragma: no cover - normal startup installs it via bootstrap.
    qrcode = None
from apis.xhs_pc_login_apis import XHSLoginApi  # noqa: E402
from spider.collect_notes import run_collection  # noqa: E402


def _cookie_string(cookies: dict) -> str:
    return "; ".join(
        f"{key}={value}" for key, value in cookies.items() if value is not None
    )


def _write_env_cookie(repo: Path, cookies: dict) -> None:
    env_path = repo / ".env"
    cookie_value = _cookie_string(cookies)
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    output = []
    replaced = False
    for line in lines:
        if line.startswith("COOKIES="):
            output.append(f"COOKIES={json.dumps(cookie_value, ensure_ascii=False)}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"COOKIES={json.dumps(cookie_value, ensure_ascii=False)}")
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _read_env_cookie(repo: Path) -> str:
    env_path = repo / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("COOKIES="):
            value = line.split("=", 1)[1].strip()
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.strip('"')
    return ""


def _safe_task_name(value: str) -> str:
    normalized = "_".join((value or "xhs_notes").strip().split())
    return "".join(ch for ch in normalized if ch not in '<>:"/\\|?*') or "xhs_notes"


def _keywords_from_search_query(value: str) -> str:
    return ",".join(item for item in (value or "").split() if item)


def _date_range_label(value: str) -> str:
    labels = {
        "recent_7_days": "近 7 天",
        "recent_30_days": "近 30 天",
    }
    return labels.get(value, value or "近 7 天")


def _open_file_url(path: Path) -> str:
    return path.resolve().as_uri()


def _default_cdp_profile_dir(repo: Path) -> Path:
    return repo / "datas" / "cache" / "xhs-note-collector-chrome"


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status=200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _html_response(handler: BaseHTTPRequestHandler, html: str) -> None:
    data = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _qr_data_uri(url: str) -> str:
    if qrcode is None:
        return ""
    import base64
    import io

    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


@dataclass
class WizardState:
    repo: Path
    output_dir: str
    search_query: str = ""
    keywords: str = ""
    date_range: str = "recent_7_days"
    max_search_candidates: int = DEFAULT_MAX_SEARCH_CANDIDATES
    auto_start: bool = False
    login_api: XHSLoginApi = field(default_factory=XHSLoginApi)
    login_cookies: dict = field(default_factory=dict)
    qr_id: str = ""
    qr_code: str = ""
    qr_url: str = ""
    qr_image: str = ""
    login_status: str = "未开始"
    cookie_ready: bool = False
    last_outputs: dict = field(default_factory=dict)
    running: bool = False
    collection_done: bool = False
    last_error: str = ""

    def __post_init__(self) -> None:
        if not self.keywords and self.search_query:
            self.keywords = _keywords_from_search_query(self.search_query)
        if _read_env_cookie(self.repo):
            self.cookie_ready = True
            self.login_status = "已检测到本地 Cookie，将优先复用"

    def default_payload(self) -> dict:
        return {
            "search_query": self.search_query,
            "keywords": self.keywords,
            "date_range": self.date_range,
            "max_search_candidates": self.max_search_candidates,
            "auto_start": self.auto_start,
        }


class WizardHandler(BaseHTTPRequestHandler):
    state: WizardState

    def log_message(self, format, *args):  # noqa: A003
        return

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            _html_response(self, PAGE_HTML)
            return
        if parsed.path == "/api/status":
            payload = {
                "login_status": self.state.login_status,
                "cookie_ready": self.state.cookie_ready,
                "running": self.state.running,
                "collection_done": self.state.collection_done,
                "last_error": self.state.last_error,
                "outputs": self.state.last_outputs,
                "defaults": self.state.default_payload(),
            }
            _json_response(self, payload)
            return
        _json_response(self, {"error": "not found"}, status=404)

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/login/start":
            self._start_login()
            return
        if parsed.path == "/api/login/check":
            self._check_login()
            return
        if parsed.path == "/api/collect":
            self._collect()
            return
        _json_response(self, {"error": "not found"}, status=404)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        data = self.rfile.read(length).decode("utf-8")
        return json.loads(data or "{}")

    def _start_login(self) -> None:
        try:
            cookies = self.state.login_api.generate_init_cookies()
            success, msg, data = self.state.login_api.generate_qrcode(cookies)
            if not success:
                raise RuntimeError(msg)
            self.state.login_cookies = data["cookies"]
            self.state.qr_id = data["qr_id"]
            self.state.qr_code = data["code"]
            self.state.qr_url = data["qr_url"]
            self.state.qr_image = _qr_data_uri(data["qr_url"])
            self.state.login_status = "请使用小红书 App 扫码登录"
            self.state.cookie_ready = False
            self.state.last_error = ""
            _json_response(
                self,
                {
                    "qr_url": self.state.qr_url,
                    "qr_image": self.state.qr_image,
                    "message": self.state.login_status,
                },
            )
        except Exception as exc:
            self.state.last_error = str(exc)
            _json_response(self, {"error": str(exc)}, status=500)

    def _check_login(self) -> None:
        try:
            if not self.state.qr_id or not self.state.qr_code:
                raise RuntimeError("请先生成登录二维码")
            success, msg, cookies = self.state.login_api.check_qrcode_status(
                self.state.qr_id,
                self.state.qr_code,
                self.state.login_cookies,
            )
            self.state.login_cookies = cookies
            self.state.login_status = msg
            if success:
                user_success, _user_info, cookies = self.state.login_api.get_user_info(cookies)
                self.state.login_cookies = cookies
                if not user_success:
                    raise RuntimeError("登录已确认，但用户信息校验失败，请重新扫码")
                _write_env_cookie(self.state.repo, cookies)
                self.state.cookie_ready = True
                self.state.login_status = "已登录，Cookie 已自动保存"
            _json_response(
                self,
                {
                    "success": success,
                    "message": self.state.login_status,
                    "cookie_ready": self.state.cookie_ready,
                },
            )
        except Exception as exc:
            self.state.last_error = str(exc)
            _json_response(self, {"error": str(exc)}, status=500)

    def _collect(self) -> None:
        if self.state.running:
            _json_response(self, {"error": "已有采集任务正在运行"}, status=409)
            return
        try:
            payload = self._read_json()
            search_query = str(payload.get("search_query") or self.state.search_query).strip()
            keywords = str(payload.get("keywords") or self.state.keywords or search_query).strip()
            date_range = str(payload.get("date_range") or self.state.date_range).strip()
            max_candidates = int(
                payload.get("max_search_candidates") or self.state.max_search_candidates
            )
            task_name = _safe_task_name(str(payload.get("task_name") or search_query))
            if not search_query:
                raise RuntimeError("请填写搜索词")
            if not keywords:
                raise RuntimeError("请填写看板关键词")
            self.state.running = True
            self.state.last_error = ""
            outputs = run_collection(
                task_name=task_name,
                search_query=search_query,
                keywords=keywords,
                date_range_value=date_range,
                max_search_candidates=max_candidates,
                output_dir=self.state.output_dir,
                mode="search",
                cookies_str=(
                    _cookie_string(self.state.login_cookies)
                    if self.state.login_cookies
                    else None
                ),
                enrich_details=True,
                cdp_profile_dir=str(_default_cdp_profile_dir(self.state.repo)),
            )
            self.state.last_outputs = {
                key: str(value) for key, value in outputs.items()
            }
            self.state.last_outputs["html_url"] = _open_file_url(Path(outputs["html"]))
            self.state.last_outputs["xlsx_url"] = _open_file_url(Path(outputs["xlsx"]))
            if outputs.get("details_dir"):
                self.state.last_outputs["details_dir_url"] = _open_file_url(
                    Path(outputs["details_dir"])
                )
            if outputs.get("detail_summary"):
                self.state.last_outputs["detail_summary_url"] = _open_file_url(
                    Path(outputs["detail_summary"])
                )
            self.state.collection_done = True
            _json_response(self, {"outputs": self.state.last_outputs})
        except Exception as exc:
            self.state.last_error = str(exc)
            _json_response(self, {"error": str(exc)}, status=500)
        finally:
            self.state.running = False


PAGE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>小红书笔记采集向导</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090d14;
      --panel: #121a27;
      --panel-2: #182337;
      --line: #2b3850;
      --text: #f3f6fb;
      --muted: #9aacbf;
      --accent: #d8b76e;
      --good: #74d4bf;
      --bad: #ff7676;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
      letter-spacing: 0;
    }
    main { max-width: 980px; margin: 0 auto; padding: 32px 20px 48px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    h2 { margin: 0 0 14px; font-size: 18px; }
    h3 { margin: 0 0 10px; font-size: 15px; }
    p { color: var(--muted); line-height: 1.7; margin: 0; }
    .header { margin-bottom: 22px; }
    .steps { display: grid; gap: 14px; }
    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 18px;
    }
    .row { display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; }
    .qr {
      width: 220px;
      height: 220px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: #111827;
      overflow: hidden;
    }
    .qr img { width: 100%; height: 100%; object-fit: contain; }
    .status { margin-top: 12px; color: var(--accent); }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0d1420;
      padding: 12px;
      min-width: 0;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .metric strong {
      display: block;
      color: var(--text);
      font-size: 14px;
      word-break: break-word;
    }
    label { display: block; margin: 12px 0 6px; color: var(--muted); font-size: 13px; }
    input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0d1420;
      color: var(--text);
      padding: 11px 12px;
      outline: none;
      font-size: 14px;
    }
    button, a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      color: var(--text);
      text-decoration: none;
      padding: 9px 14px;
      cursor: pointer;
      font-size: 14px;
    }
    button.primary, a.primary { border-color: var(--accent); color: var(--accent); }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    .actions { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
    .result { display: none; margin-top: 14px; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: #0d1420; }
    .error { color: var(--bad); margin-top: 10px; }
    .ok { color: var(--good); }
    @media (max-width: 720px) {
      main { padding: 22px 14px 36px; }
      .qr { width: 180px; height: 180px; }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <main>
    <section class="header">
      <h1>小红书笔记采集向导</h1>
      <p>页面打开后会自动检查登录状态。没有登录时只需要用小红书 App 扫码，登录成功后会自动开始采集并生成结果。</p>
    </section>
    <section class="steps">
      <div class="panel">
        <h2>本次采集</h2>
        <div class="summary">
          <div class="metric"><span>搜索词</span><strong id="summarySearch">待填写</strong></div>
          <div class="metric"><span>看板关键词</span><strong id="summaryKeywords">待填写</strong></div>
          <div class="metric"><span>时间范围</span><strong id="summaryDate">近 7 天</strong></div>
          <div class="metric"><span>最多检查</span><strong id="summaryMax">50</strong></div>
        </div>
      </div>
      <div class="panel">
        <h2>登录小红书</h2>
        <div class="row">
          <div class="qr" id="qrBox">正在准备登录</div>
          <div style="min-width:260px; flex:1;">
            <p>如果本机已有可用登录态，工具会直接继续。否则请用小红书 App 扫码并在手机上确认登录。</p>
            <div class="actions">
              <button class="primary" id="startLogin">重新生成二维码</button>
            </div>
            <div class="status" id="loginStatus">未登录</div>
          </div>
        </div>
      </div>
      <div class="panel">
        <h2>采集进度</h2>
        <p id="collectHint">等待任务信息。</p>
        <label for="searchQuery">小红书搜索词</label>
        <input id="searchQuery" placeholder="例如：大超炮 北京">
        <label for="keywords">看板关键词，用英文逗号分隔</label>
        <input id="keywords" placeholder="例如：大超炮,北京">
        <label for="dateRange">时间范围</label>
        <select id="dateRange">
          <option value="recent_7_days">近 7 天</option>
          <option value="recent_30_days">近 30 天</option>
        </select>
        <label for="maxCandidates">最多检查多少条搜索候选</label>
        <input id="maxCandidates" type="number" value="50" min="1" max="5000">
        <div class="actions">
          <button class="primary" id="runCollect">开始采集并生成看板</button>
        </div>
        <div class="error" id="error"></div>
        <div class="result" id="result"></div>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let timer = null;
    let defaults = {};
    let collectionStarted = false;
    let loginStarted = false;
    let cookieReady = false;

    async function postJson(url, payload = {}) {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '请求失败');
      return data;
    }

    async function getJson(url) {
      const response = await fetch(url);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '请求失败');
      return data;
    }

    function dateLabel(value) {
      if (value === 'recent_30_days') return '近 30 天';
      if (value === 'recent_7_days' || !value) return '近 7 天';
      return value;
    }

    function syncSummary() {
      $('summarySearch').textContent = $('searchQuery').value || '待填写';
      $('summaryKeywords').textContent = $('keywords').value || '待填写';
      $('summaryDate').textContent = dateLabel($('dateRange').value);
      $('summaryMax').textContent = $('maxCandidates').value || '50';
    }

    function payloadFromForm() {
      return {
        search_query: $('searchQuery').value,
        keywords: $('keywords').value,
        date_range: $('dateRange').value,
        max_search_candidates: $('maxCandidates').value,
        task_name: $('searchQuery').value
      };
    }

    function fillDefaults(payload) {
      defaults = payload || {};
      $('searchQuery').value = defaults.search_query || '';
      $('keywords').value = defaults.keywords || '';
      $('dateRange').value = defaults.date_range || 'recent_7_days';
      $('maxCandidates').value = defaults.max_search_candidates || 50;
      syncSummary();
      if (defaults.search_query) {
        $('collectHint').textContent = '任务已准备好，登录完成后会自动开始。';
      } else {
        $('collectHint').textContent = '请填写搜索词后开始采集。';
      }
    }

    function showOutputs(outputs) {
      $('result').style.display = 'block';
      $('result').innerHTML = `
        <div class="ok">采集完成</div>
        <div class="actions">
          <a class="button primary" href="${outputs.html_url}" target="_blank">打开 HTML 看板</a>
          <a class="button" href="${outputs.xlsx_url}" target="_blank">打开 Excel</a>
          ${outputs.details_dir_url ? `<a class="button" href="${outputs.details_dir_url}" target="_blank">打开正文目录</a>` : ''}
          ${outputs.detail_summary_url ? `<a class="button" href="${outputs.detail_summary_url}" target="_blank">打开详情报告</a>` : ''}
        </div>
        <p>HTML：${outputs.html}</p>
        <p>Excel：${outputs.xlsx}</p>
        ${outputs.details_dir ? `<p>Markdown 正文：${outputs.details_dir}</p>` : ''}
        ${outputs.detail_summary ? `<p>详情报告：${outputs.detail_summary}</p>` : ''}
      `;
    }

    async function checkLogin() {
      const data = await postJson('/api/login/check');
      $('loginStatus').textContent = data.message || '检查完成';
      $('loginStatus').className = data.cookie_ready ? 'status ok' : 'status';
      cookieReady = data.cookie_ready;
      if (cookieReady && timer) {
        clearInterval(timer);
        timer = null;
      }
      maybeAutoCollect();
    }

    async function startLogin() {
      $('error').textContent = '';
      loginStarted = true;
      const data = await postJson('/api/login/start');
      $('qrBox').innerHTML = data.qr_image
        ? `<img src="${data.qr_image}" alt="登录二维码">`
        : `<a href="${data.qr_url}" target="_blank">打开登录二维码</a>`;
      $('loginStatus').textContent = data.message;
      if (timer) clearInterval(timer);
      timer = setInterval(() => checkLogin().catch(() => {}), 3000);
    }

    async function runCollect() {
      if (collectionStarted) return;
      syncSummary();
      collectionStarted = true;
      $('error').textContent = '';
      $('result').style.display = 'block';
      $('result').textContent = '采集中，并使用浏览器补全笔记正文，请稍等...';
      $('collectHint').textContent = '正在采集列表并补全正文。';
      $('runCollect').disabled = true;
      try {
        const data = await postJson('/api/collect', payloadFromForm());
        showOutputs(data.outputs);
        $('collectHint').textContent = '已完成，优先查看 HTML 看板。';
      } catch (error) {
        collectionStarted = false;
        $('result').textContent = '';
        $('error').textContent = error.message;
        $('collectHint').textContent = '采集未完成，请根据错误提示处理后重试。';
      } finally {
        $('runCollect').disabled = false;
      }
    }

    function maybeAutoCollect() {
      if (collectionStarted || !defaults.auto_start || !cookieReady || !$('searchQuery').value) {
        return;
      }
      runCollect();
    }

    async function init() {
      try {
        const status = await getJson('/api/status');
        fillDefaults(status.defaults || {});
        cookieReady = status.cookie_ready;
        $('loginStatus').textContent = status.login_status || '未登录';
        $('loginStatus').className = cookieReady ? 'status ok' : 'status';
        if (status.outputs && status.outputs.html_url) showOutputs(status.outputs);
        if (cookieReady) {
          $('qrBox').textContent = '已登录';
          maybeAutoCollect();
        } else if (defaults.auto_start || defaults.search_query) {
          startLogin().catch((error) => $('error').textContent = error.message);
        }
      } catch (error) {
        $('error').textContent = error.message;
      }
    }

    ['searchQuery', 'keywords', 'dateRange', 'maxCandidates'].forEach((id) => {
      $(id).addEventListener('input', syncSummary);
      $(id).addEventListener('change', syncSummary);
    });
    $('startLogin').addEventListener('click', () => {
      startLogin().catch((error) => $('error').textContent = error.message);
    });
    $('runCollect').addEventListener('click', () => runCollect());
    init();
  </script>
</body>
</html>
"""


def parse_args():
    parser = argparse.ArgumentParser(description="启动小红书笔记采集网页向导")
    parser.add_argument(
        "--repo",
        help="兼容旧脚本参数；网页向导默认使用 skill 内置 runtime，高级调试请用 XHS_NOTE_COLLECTOR_REPO 覆盖",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--output-dir", default="datas/batch_outputs")
    parser.add_argument("--search-query", help="预填并采集的小红书搜索词")
    parser.add_argument("--keywords", help="预填看板关键词，默认从搜索词按空格拆分")
    parser.add_argument("--date-range", default="recent_7_days", help="recent_7_days/recent_30_days")
    parser.add_argument("--max-search-candidates", type=int, default=DEFAULT_MAX_SEARCH_CANDIDATES)
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="浏览器打开后自动准备登录，登录完成后自动开始采集",
    )
    parser.add_argument("--no-open", action="store_true", help="只启动服务，不自动打开浏览器")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.repo and Path(args.repo).expanduser().resolve() != REPO_ROOT:
        raise SystemExit(
            "网页向导默认使用 skill 内置 runtime；如需开发调试外部仓库，"
            "请先设置 XHS_NOTE_COLLECTOR_REPO 后再启动。"
        )
    repo = REPO_ROOT
    if not (repo / "spider" / "collect_notes.py").exists():
        raise SystemExit(f"未找到小红书采集运行时: {repo}")
    if not os.getenv("XHS_NOTE_COLLECTOR_SKIP_BOOTSTRAP"):
        BOOTSTRAP.ensure_environment(repo)
    port = args.port or _free_port()
    state = WizardState(
        repo=repo,
        output_dir=args.output_dir,
        search_query=args.search_query or "",
        keywords=args.keywords or "",
        date_range=args.date_range,
        max_search_candidates=args.max_search_candidates,
        auto_start=args.auto_start or bool(args.search_query),
    )
    handler = type("BoundWizardHandler", (WizardHandler,), {"state": state})
    server = ThreadingHTTPServer((args.host, port), handler)
    url = f"http://{args.host}:{port}/"
    print(f"小红书笔记采集向导已启动: {url}")
    if not args.no_open:
        threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止采集向导")
    finally:
        server.server_close()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
