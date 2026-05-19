from __future__ import annotations

import html
import json
from pathlib import Path

import openpyxl


SUMMARY_SHEET = "命中帖子汇总"
SORT_FIELDS = [
    ("liked_count", "点赞"),
    ("comment_count", "评论"),
    ("share_count", "转发"),
    ("collected_count", "收藏"),
]


def _read_summary_rows(xlsx_path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        if SUMMARY_SHEET not in wb.sheetnames:
            raise ValueError(f"Excel 缺少 sheet: {SUMMARY_SHEET}")
        ws = wb[SUMMARY_SHEET]
        rows = ws.iter_rows(values_only=True)
        headers = [str(value or "") for value in next(rows, [])]
        result = []
        for row in rows:
            item = {}
            for index, header in enumerate(headers):
                item[header] = row[index] if index < len(row) else ""
            if item.get("note_id"):
                result.append(item)
        return result
    finally:
        wb.close()


def _metric_value(value) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    multipliers = {"万": 10000, "千": 1000, "k": 1000, "K": 1000, "w": 10000, "W": 10000}
    suffix = text[-1]
    try:
        if suffix in multipliers:
            return int(float(text[:-1]) * multipliers[suffix])
        return int(float(text))
    except ValueError:
        return 0


def _safe_text(value) -> str:
    return "" if value is None else str(value)


def _detail_url(path_value: str) -> str:
    if not path_value:
        return ""
    return Path(path_value).resolve().as_uri()


def _dashboard_payload(rows: list[dict], detail_index: dict | None = None) -> list[dict]:
    detail_index = detail_index or {}
    payload = []
    for row in rows:
        item = {key: _safe_text(row.get(key, "")) for key in row}
        detail = detail_index.get(item.get("note_id", "")) or {}
        item["detail_export_status"] = _safe_text(detail.get("status", ""))
        item["detail_error"] = _safe_text(detail.get("error", ""))
        item["detail_md_url"] = _detail_url(_safe_text(detail.get("md_path", "")))
        for key, _label in SORT_FIELDS:
            item[f"{key}_num"] = _metric_value(row.get(key))
        payload.append(item)
    return payload


def _render_html(rows: list[dict], title: str, detail_index: dict | None = None) -> str:
    payload = _dashboard_payload(rows, detail_index=detail_index)
    payload_json = json.dumps(payload, ensure_ascii=False)
    escaped_title = html.escape(title)
    total_likes = sum(item["liked_count_num"] for item in payload)
    total_comments = sum(item["comment_count_num"] for item in payload)
    total_shares = sum(item["share_count_num"] for item in payload)
    total_collects = sum(item["collected_count_num"] for item in payload)
    sort_buttons = "\n".join(
        f'<button type="button" data-sort-key="{key}">{label}</button>'
        for key, label in SORT_FIELDS
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0f17;
      --panel: #111827;
      --panel-soft: #162033;
      --line: #273244;
      --text: #eef2f7;
      --muted: #93a4b8;
      --accent: #d7b46a;
      --accent-2: #67d7c4;
      --danger: #ff7676;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #0b0f17;
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
      letter-spacing: 0;
    }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 28px; }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 20px;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 8px; font-size: 26px; font-weight: 700; }}
    .subtle {{ color: var(--muted); font-size: 13px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, minmax(110px, 1fr));
      gap: 10px;
      margin: 22px 0;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .stat span {{ display: block; color: var(--muted); font-size: 12px; }}
    .stat strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
      padding: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .sorts {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    button {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      color: var(--text);
      padding: 8px 12px;
      cursor: pointer;
      font-size: 13px;
    }}
    button.active {{ border-color: var(--accent); color: var(--accent); }}
    input {{
      min-width: 260px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0d1421;
      color: var(--text);
      padding: 9px 12px;
      outline: none;
    }}
    .note-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .list-row {{
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr) minmax(330px, 0.45fr);
      gap: 14px;
      min-height: 124px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      align-items: stretch;
    }}
    .list-row:hover {{
      border-color: #3a4b64;
      background: #131d2e;
    }}
    .cover {{
      width: 92px;
      height: 108px;
      object-fit: cover;
      border-radius: 6px;
      background: #0d1421;
      border: 1px solid var(--line);
    }}
    .title {{
      display: block;
      color: var(--text);
      text-decoration: none;
      font-size: 15px;
      line-height: 1.45;
      font-weight: 650;
      margin-bottom: 8px;
    }}
    .row-main {{
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}
    .row-side {{
      display: grid;
      grid-template-rows: 1fr auto;
      gap: 10px;
      min-width: 0;
    }}
    .meta, .keywords {{ color: var(--muted); font-size: 12px; line-height: 1.6; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 10px; }}
    .metric {{
      background: #0d1421;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 8px;
      font-size: 12px;
    }}
    .metric b {{ color: var(--accent-2); font-size: 13px; }}
    .row-actions {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
    }}
    .badge {{
      display: inline-block;
      color: var(--accent);
      font-size: 12px;
    }}
    .open-link {{
      color: var(--text);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0d1421;
      padding: 7px 10px;
      white-space: nowrap;
    }}
    .open-link:hover {{ border-color: var(--accent); color: var(--accent); }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px; }}
      header, .toolbar {{ align-items: stretch; flex-direction: column; }}
      .stats {{ grid-template-columns: repeat(2, 1fr); }}
      input {{ min-width: 100%; width: 100%; }}
      .list-row {{ grid-template-columns: 78px 1fr; }}
      .row-side {{ grid-column: 1 / -1; }}
      .cover {{ width: 78px; height: 96px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <h1>{escaped_title}</h1>
        <div class="subtle">基于导出的 XLSX 生成，未改动原始数据；列表数据来自小红书搜索结果。</div>
      </div>
      <div class="subtle">排序默认按点赞降序</div>
    </header>
    <section class="stats">
      <div class="stat"><span>笔记数</span><strong>{len(payload)}</strong></div>
      <div class="stat"><span>点赞</span><strong>{total_likes}</strong></div>
      <div class="stat"><span>评论</span><strong>{total_comments}</strong></div>
      <div class="stat"><span>转发</span><strong>{total_shares}</strong></div>
      <div class="stat"><span>收藏</span><strong>{total_collects}</strong></div>
    </section>
    <section class="toolbar">
      <div class="sorts">{sort_buttons}</div>
      <input id="filter" type="search" placeholder="筛选标题、作者、关键词">
    </section>
    <section id="notes" class="note-list"></section>
  </main>
  <script>
    const notes = {payload_json};
    const noteList = document.querySelector('#notes');
    const filter = document.querySelector('#filter');
    const buttons = Array.from(document.querySelectorAll('button[data-sort-key]'));
    let sortKey = 'liked_count';

    function esc(value) {{
      return String(value ?? '').replace(/[&<>"']/g, ch => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }}[ch]));
    }}
    function metric(label, value) {{
      return `<div class="metric">${{label}}<br><b>${{esc(value || '0')}}</b></div>`;
    }}
    function render() {{
      const query = filter.value.trim().toLowerCase();
      const filtered = notes
        .filter(note => !query || [note.title, note.author_nickname, note.matched_keywords]
          .join(' ').toLowerCase().includes(query))
        .sort((a, b) => (b[`${{sortKey}}_num`] || 0) - (a[`${{sortKey}}_num`] || 0));
      noteList.innerHTML = filtered.map(note => `
        <article class="list-row">
          <img class="cover" src="${{esc(note.cover_url)}}" alt="">
          <div class="row-main">
            <a class="title" href="${{esc(note.note_url)}}" target="_blank" rel="noreferrer">${{esc(note.title || '无标题')}}</a>
            <div class="meta">${{esc(note.author_nickname || '未知作者')}} · ${{esc(note.publish_time_text || note.publish_time || '时间未知')}} · ${{esc(note.note_type || '')}}</div>
            <div class="keywords">命中：${{esc(note.matched_keywords || '')}}</div>
          </div>
          <div class="row-side">
            <div class="metrics">
              ${{metric('点赞', note.liked_count)}}
              ${{metric('评论', note.comment_count)}}
              ${{metric('转发', note.share_count)}}
              ${{metric('收藏', note.collected_count)}}
            </div>
            <div class="row-actions">
              <span class="badge">${{esc(note.detail_export_status || note.detail_status || '')}}</span>
              ${{note.detail_md_url
                ? `<a class="open-link" href="${{esc(note.detail_md_url)}}" target="_blank" rel="noreferrer">打开正文</a>`
                : (note.detail_error ? `<span class="badge">${{esc(note.detail_error)}}</span>` : '')}}
              <a class="open-link" href="${{esc(note.note_url)}}" target="_blank" rel="noreferrer">打开笔记</a>
            </div>
          </div>
        </article>
      `).join('');
    }}
    buttons.forEach(button => {{
      button.addEventListener('click', () => {{
        sortKey = button.dataset.sortKey;
        buttons.forEach(item => item.classList.toggle('active', item === button));
        render();
      }});
    }});
    filter.addEventListener('input', render);
    buttons[0]?.classList.add('active');
    render();
  </script>
</body>
</html>
"""


def build_dashboard_from_xlsx(xlsx_path, html_path=None, detail_index=None):
    xlsx_path = Path(xlsx_path)
    rows = _read_summary_rows(xlsx_path)
    html_path = Path(html_path) if html_path else xlsx_path.with_suffix(".html")
    title = xlsx_path.stem.replace("小红书采集_", "小红书笔记看板 ")
    html_path.write_text(
        _render_html(rows, title=title, detail_index=detail_index),
        encoding="utf-8",
    )
    return html_path
