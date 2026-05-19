from __future__ import annotations

import asyncio
import http.cookies
import importlib.util
import json
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import aiohttp


def _load_bootstrap():
    path = Path(__file__).resolve().parents[1] / ".." / "scripts" / "bootstrap.py"
    path = path.resolve()
    spec = importlib.util.spec_from_file_location("xhs_note_collector_bootstrap", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_chrome_executable() -> str:
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    bootstrap = _load_bootstrap()
    chrome_path = bootstrap.find_chrome_executable()
    if not chrome_path:
        raise RuntimeError("未找到 Google Chrome。详情补全依赖 Chrome，请先安装 Chrome。")
    return chrome_path


LOGIN_URL = "https://www.xiaohongshu.com/"
INVALID_FILENAME_CHARS = '<>:"/\\|?*'

EXTRACT_NOTE_JS = r"""
(() => {
  const unref = (x) => x && typeof x === 'object' && ('_value' in x || 'value' in x) ? (x._value ?? x.value) : x;
  const state = window.__INITIAL_STATE__ || {};
  const noteStore = state.note || {};
  const noteDetailMap = unref(noteStore.noteDetailMap) || noteStore.noteDetailMap || {};
  const noteId = unref(noteStore.firstNoteId) || unref(noteStore.currentNoteId) || Object.keys(noteDetailMap)[0] || '';
  const detail = noteId ? (noteDetailMap[noteId] || noteDetailMap[unref(noteId)]) : null;
  const note = detail && detail.note ? unref(detail.note) : null;
  const commentsObj = detail && detail.comments ? unref(detail.comments) : null;
  const comments = commentsObj && commentsObj.list ? unref(commentsObj.list) : [];
  const pickImage = (img) => {
    const infos = img && (img.infoList || img.info_list) || [];
    if (infos[1] && infos[1].url) return infos[1].url;
    if (infos[0] && infos[0].url) return infos[0].url;
    return (img && (img.urlDefault || img.url_default || img.urlPre || img.url_pre || img.url)) || '';
  };
  const images = note && (note.imageList || note.image_list) ? (note.imageList || note.image_list).map(pickImage).filter(Boolean) : [];
  return JSON.stringify({
    pageUrl: location.href,
    pageTitle: document.title,
    readyState: document.readyState,
    hasState: !!window.__INITIAL_STATE__,
    noteId: unref(noteId),
    note: note ? {
      noteId: note.noteId || note.note_id || unref(noteId),
      title: note.title || '',
      desc: note.desc || '',
      type: note.type || '',
      time: note.time || 0,
      ipLocation: note.ipLocation || note.ip_location || '',
      user: note.user ? {
        nickname: note.user.nickname || '',
        userId: note.user.userId || note.user.user_id || '',
        avatar: note.user.avatar || ''
      } : {},
      tags: (note.tagList || note.tag_list || []).map(t => t.name).filter(Boolean),
      interact: note.interactInfo || note.interact_info || {},
      images
    } : null,
    comments: (comments || []).slice(0, 20).map(c => ({
      id: c.id || '',
      content: c.content || '',
      createTime: c.createTime || c.create_time || 0,
      ipLocation: c.ipLocation || c.ip_location || '',
      likeCount: c.likeCount || c.like_count || '',
      user: c.userInfo || c.user_info ? {
        nickname: (c.userInfo || c.user_info).nickname || '',
        userId: (c.userInfo || c.user_info).userId || (c.userInfo || c.user_info).user_id || ''
      } : {}
    })),
    visibleText: document.body ? document.body.innerText.slice(0, 2000) : ''
  });
})()
"""


@dataclass
class CdpExportResult:
    md_dir: Path
    jsonl: Path
    summary: Path
    detail_index: Dict[str, Dict[str, Any]]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _safe_filename_part(value: str) -> str:
    safe_value = str(value or "").strip()
    for char in INVALID_FILENAME_CHARS:
        safe_value = safe_value.replace(char, "_")
    return safe_value or "untitled"


def _encode_cdp_url(value: str) -> str:
    return urllib.parse.quote(value, safe=":/%")


def _cookies_from_string(cookies_str: str | None) -> Dict[str, str]:
    if not cookies_str:
        return {}
    parsed: Dict[str, str] = {}
    try:
        cookie = http.cookies.SimpleCookie()
        cookie.load(cookies_str)
        parsed.update({key: morsel.value for key, morsel in cookie.items()})
    except Exception:
        parsed = {}
    if parsed:
        return parsed
    for item in str(cookies_str).split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if key:
            parsed[key] = value.strip()
    return parsed


def _fmt_time(ms: Any) -> str:
    try:
        timestamp_ms = int(ms or 0)
    except (TypeError, ValueError):
        timestamp_ms = 0
    if not timestamp_ms:
        return ""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _count_tokens(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text or ""))
    except Exception:
        return 0


def _markdown_for_detail(data: dict) -> str:
    note = data.get("note") or {}
    user = note.get("user") or {}
    interact = note.get("interact") or {}
    title = note.get("title") or data.get("pageTitle") or "无标题"
    note_type = "图集" if note.get("type") == "normal" else note.get("type", "")
    tags = "，".join(note.get("tags") or []) if note.get("tags") else "无"
    lines = [
        f"# {title}",
        "",
        "> 来源：CDP 读取小红书真实 Chrome 页面状态。",
        "",
        "## 基本信息",
        "",
        f"- 笔记ID：{note.get('noteId') or data.get('noteId') or ''}",
        f"- 页面URL：{data.get('pageUrl') or ''}",
        f"- 类型：{note_type}",
        f"- 作者：{user.get('nickname', '')}（{user.get('userId', '')}）",
        f"- 发布时间：{_fmt_time(note.get('time'))}",
        f"- IP属地：{note.get('ipLocation') or '未知'}",
        f"- 标签：{tags}",
        "- 互动："
        f"点赞 {interact.get('likedCount', interact.get('liked_count', ''))} / "
        f"收藏 {interact.get('collectedCount', interact.get('collected_count', ''))} / "
        f"评论 {interact.get('commentCount', interact.get('comment_count', ''))} / "
        f"分享 {interact.get('shareCount', interact.get('share_count', ''))}",
        "",
        "## 正文",
        "",
        note.get("desc") or "",
        "",
    ]
    images = note.get("images") or []
    if images:
        lines.extend(["## 图片", ""])
        for index, url in enumerate(images, 1):
            lines.extend([f"![图片{index}]({url})", ""])
    comments = data.get("comments") or []
    if comments:
        lines.extend(["## 评论", ""])
        for index, comment in enumerate(comments, 1):
            content = comment.get("content") or ""
            if not content:
                continue
            meta = []
            if comment.get("createTime"):
                meta.append(_fmt_time(comment["createTime"]))
            if comment.get("ipLocation"):
                meta.append(str(comment["ipLocation"]))
            if str(comment.get("likeCount", "")) != "":
                meta.append(f"赞 {comment.get('likeCount')}")
            suffix = f"（{'，'.join(meta)}）" if meta else ""
            nickname = (comment.get("user") or {}).get("nickname", "")
            lines.append(f"{index}. {nickname}：{content}{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


class ChromeCdpClient:
    def __init__(
        self,
        *,
        profile_dir: str | Path,
        port: int | None = None,
        chrome_path: str | None = None,
        startup_url: str = LOGIN_URL,
        request_timeout: int = 10,
        nav_wait_seconds: float = 1.8,
        eval_retries: int = 8,
        eval_wait_seconds: float = 0.5,
        cookies_str: str | None = None,
    ):
        self.profile_dir = Path(profile_dir)
        self.port = port or _free_port()
        self.chrome_path = chrome_path
        self.startup_url = startup_url
        self.request_timeout = request_timeout
        self.nav_wait_seconds = nav_wait_seconds
        self.eval_retries = eval_retries
        self.eval_wait_seconds = eval_wait_seconds
        self.cookies_str = cookies_str
        self._cookies_applied = False
        self.process: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def ensure_ready(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if not self._devtools_available():
            self._launch_chrome()
        self._wait_for_devtools()
        self._apply_cookie_string()

    def open_login_page(self) -> None:
        self.ensure_ready()
        self._http_json(
            "/json/new?" + _encode_cdp_url(self.startup_url),
            method="PUT",
        )

    def extract_note(self, url: str) -> dict:
        self.ensure_ready()
        target = self._create_target(url)
        target_id = target.get("id")
        web_socket_url = target.get("webSocketDebuggerUrl")
        if not target_id or not web_socket_url:
            raise RuntimeError(f"CDP target 创建失败: {target}")
        try:
            time.sleep(self.nav_wait_seconds)
            last_error = None
            for _attempt in range(self.eval_retries):
                try:
                    data = asyncio.run(self._evaluate_note(web_socket_url))
                    note = data.get("note") or {}
                    if note.get("title") or note.get("desc"):
                        return data
                    last_error = RuntimeError("页面尚未出现笔记内容")
                except Exception as exc:
                    last_error = exc
                time.sleep(self.eval_wait_seconds)
            raise RuntimeError(f"CDP 抽取失败: {last_error}")
        finally:
            self._close_target(target_id)

    def close(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _launch_chrome(self) -> None:
        chrome_path = self.chrome_path or _find_chrome_executable()
        if not Path(chrome_path).exists():
            raise RuntimeError(f"未找到 Google Chrome: {chrome_path}")
        cmd = [
            chrome_path,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            self.startup_url,
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _devtools_available(self) -> bool:
        try:
            self._http_json("/json/version", timeout=1)
            return True
        except Exception:
            return False

    def _wait_for_devtools(self) -> None:
        deadline = time.time() + 15
        while time.time() < deadline:
            if self._devtools_available():
                return
            time.sleep(0.25)
        raise RuntimeError("Chrome CDP 未能启动，请检查 Chrome 是否可用")

    def _create_target(self, url: str) -> dict:
        encoded = _encode_cdp_url(url)
        try:
            return self._http_json(f"/json/new?{encoded}", method="PUT")
        except urllib.error.HTTPError:
            return self._http_json(f"/json/new?{encoded}")

    def _apply_cookie_string(self) -> None:
        cookies = _cookies_from_string(self.cookies_str)
        if self._cookies_applied or not cookies:
            return
        target = self._create_target(LOGIN_URL)
        target_id = target.get("id")
        web_socket_url = target.get("webSocketDebuggerUrl")
        if not target_id or not web_socket_url:
            raise RuntimeError(f"CDP Cookie target 创建失败: {target}")
        try:
            asyncio.run(self._set_cookies(web_socket_url, cookies))
            self._cookies_applied = True
        finally:
            self._close_target(target_id)

    def _close_target(self, target_id: str) -> None:
        try:
            self._http_json(f"/json/close/{target_id}", timeout=3)
        except Exception:
            pass

    def _http_json(
        self,
        path: str,
        timeout: int | None = None,
        method: str = "GET",
    ) -> dict:
        request = urllib.request.Request(self.base_url + path, method=method)
        with urllib.request.urlopen(request, timeout=timeout or self.request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    async def _evaluate_note(self, web_socket_url: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(web_socket_url, timeout=self.request_timeout) as ws:
                await ws.send_json(
                    {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": EXTRACT_NOTE_JS,
                            "awaitPromise": False,
                            "returnByValue": True,
                        },
                    }
                )
                async for message in ws:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(message.data)
                        if payload.get("id") != 1:
                            continue
                        if payload.get("error"):
                            raise RuntimeError(payload["error"])
                        result = payload.get("result", {}).get("result", {})
                        value = result.get("value")
                        if not value:
                            raise RuntimeError(f"CDP evaluate 无返回: {payload}")
                        return json.loads(value)
                    if message.type == aiohttp.WSMsgType.ERROR:
                        raise RuntimeError(f"CDP websocket 错误: {ws.exception()}")
        raise RuntimeError("CDP websocket 已关闭")

    async def _set_cookies(self, web_socket_url: str, cookies: Dict[str, str]) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(web_socket_url, timeout=self.request_timeout) as ws:
                command_id = 1
                for name, value in cookies.items():
                    await ws.send_json(
                        {
                            "id": command_id,
                            "method": "Network.setCookie",
                            "params": {
                                "name": name,
                                "value": value,
                                "domain": ".xiaohongshu.com",
                                "path": "/",
                                "secure": True,
                            },
                        }
                    )
                    async for message in ws:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            payload = json.loads(message.data)
                            if payload.get("id") != command_id:
                                continue
                            if payload.get("error"):
                                raise RuntimeError(payload["error"])
                            success = payload.get("result", {}).get("success", True)
                            if not success:
                                raise RuntimeError(f"CDP Cookie 写入失败: {name}")
                            break
                        if message.type == aiohttp.WSMsgType.ERROR:
                            raise RuntimeError(f"CDP websocket 错误: {ws.exception()}")
                    command_id += 1


def export_note_details(
    *,
    notes: Iterable[Any],
    output_dir: str | Path,
    task_name: str,
    cdp_client: Any | None = None,
    timestamp: str | None = None,
    cdp_profile_dir: str | Path | None = None,
    cookies_str: str | None = None,
    close_client: bool = True,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"小红书详情_{_safe_filename_part(task_name)}_{timestamp}"
    md_dir = output_path / f"{base_name}_md"
    md_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_path / f"{base_name}.details.jsonl"
    summary_path = output_path / f"{base_name}.details.summary.json"
    client = cdp_client or ChromeCdpClient(
        profile_dir=cdp_profile_dir or (output_path.parent / "cache" / "xhs-cdp-profile"),
        cookies_str=cookies_str,
    )
    detail_index: Dict[str, Dict[str, Any]] = {}
    rows = []
    start = time.perf_counter()

    client.ensure_ready()
    for index, note in enumerate(notes, 1):
        note_id = getattr(note, "note_id", "") or f"idx_{index}"
        note_url = getattr(note, "note_url", "")
        item_start = time.perf_counter()
        row = {
            "index": index,
            "note_id": note_id,
            "url": note_url,
            "status": "unknown",
            "error": "",
            "elapsed_ms": 0,
        }
        try:
            data = client.extract_note(note_url)
            note_data = data.get("note") or {}
            if not (note_data.get("title") or note_data.get("desc")):
                raise RuntimeError("CDP 未提取到标题或正文")
            markdown = _markdown_for_detail(data)
            md_path = md_dir / f"{index:02d}_{_safe_filename_part(note_id)}.md"
            md_path.write_text(markdown, encoding="utf-8")
            compact_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            row.update(
                {
                    "status": "success",
                    "extracted_title": note_data.get("title") or "",
                    "desc_len": len(note_data.get("desc") or ""),
                    "image_count": len(note_data.get("images") or []),
                    "comment_count": len(data.get("comments") or []),
                    "compact_json_chars": len(compact_json),
                    "compact_json_tokens": _count_tokens(compact_json),
                    "md_chars": len(markdown),
                    "md_tokens": _count_tokens(markdown),
                    "md_path": str(md_path),
                    "source": data,
                }
            )
        except Exception as exc:
            row.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        finally:
            row["elapsed_ms"] = round((time.perf_counter() - item_start) * 1000)
            rows.append(row)
            detail_index[note_id] = {
                key: value
                for key, value in row.items()
                if key not in ("source",)
            }

    if close_client:
        client.close()

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    success_rows = [row for row in rows if row.get("status") == "success"]
    summary = {
        "task_name": task_name,
        "total": len(rows),
        "success": len(success_rows),
        "failed": len(rows) - len(success_rows),
        "elapsed_ms_total": round((time.perf_counter() - start) * 1000),
        "elapsed_ms_avg_success": (
            round(sum(row.get("elapsed_ms", 0) for row in success_rows) / len(success_rows), 1)
            if success_rows
            else None
        ),
        "md_tokens_avg_success": (
            round(sum(row.get("md_tokens", 0) for row in success_rows) / len(success_rows), 1)
            if success_rows
            else None
        ),
        "jsonl": str(jsonl_path),
        "md_dir": str(md_dir),
        "detail_index": detail_index,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "md_dir": md_dir,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "detail_index": detail_index,
    }
