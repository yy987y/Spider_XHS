import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

import openpyxl


SUMMARY_HEADERS = [
    "note_id",
    "note_url",
    "cover_url",
    "title",
    "desc",
    "tags",
    "author_nickname",
    "author_user_id",
    "red_id",
    "publish_time",
    "liked_count",
    "collected_count",
    "comment_count",
    "share_count",
    "matched_keywords",
    "matched_in_title",
    "matched_in_desc",
    "matched_in_tags",
    "sources",
    "search_query",
    "crawl_time",
]

KEYWORD_HEADERS = SUMMARY_HEADERS + ["keyword"]

EVENT_HEADERS = [
    "level",
    "event_type",
    "message",
    "channel",
    "red_id",
    "search_query",
    "page",
    "count",
    "extra",
    "created_at",
]


def _json_default(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if is_dataclass(value):
        return asdict(value)
    return str(value)


def _cell(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, list):
        return "，".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    return value


def _append_dict_rows(ws, headers, rows):
    ws.append(headers)
    for row in rows:
        if is_dataclass(row):
            row = asdict(row)
        ws.append([_cell(row.get(header, "")) for header in headers])


def _note_to_dict(note):
    return asdict(note)


def build_keyword_rows(notes):
    rows = []
    for note in notes:
        payload = _note_to_dict(note)
        for keyword in note.matched_keywords:
            row = dict(payload)
            row["keyword"] = keyword
            rows.append(row)
    return rows


def write_outputs(
    notes,
    keyword_rows,
    stats_rows,
    events,
    output_dir,
    task_name,
    timestamp=None,
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"小红书采集_{task_name}_{timestamp}"
    xlsx_path = output_path / f"{base_name}.xlsx"
    jsonl_path = output_path / f"{base_name}.jsonl"
    log_jsonl_path = output_path / f"{base_name}.logs.jsonl"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "命中帖子汇总"
    _append_dict_rows(ws, SUMMARY_HEADERS, [_note_to_dict(note) for note in notes])

    ws_keyword = wb.create_sheet("按关键词展开明细")
    _append_dict_rows(ws_keyword, KEYWORD_HEADERS, keyword_rows or build_keyword_rows(notes))

    ws_stats = wb.create_sheet("采集统计")
    stat_headers = (
        sorted({key for row in stats_rows for key in row.keys()})
        if stats_rows
        else ["metric", "value"]
    )
    _append_dict_rows(ws_stats, stat_headers, stats_rows)

    ws_events = wb.create_sheet("异常与边界日志")
    _append_dict_rows(ws_events, EVENT_HEADERS, events)

    wb.save(xlsx_path)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for note in notes:
            f.write(json.dumps(note, ensure_ascii=False, default=_json_default) + "\n")

    with log_jsonl_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, default=_json_default) + "\n")

    return {"xlsx": xlsx_path, "jsonl": jsonl_path, "log_jsonl": log_jsonl_path}
