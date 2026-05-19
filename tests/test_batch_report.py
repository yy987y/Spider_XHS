import json
from datetime import datetime

import openpyxl

from spider.batch_models import CollectedNote, CrawlEvent
from spider.batch_report import write_outputs


def cell_value_by_header(ws, row_number, header):
    headers = [cell.value for cell in ws[1]]
    return ws.cell(row=row_number, column=headers.index(header) + 1).value


def test_write_outputs_creates_workbook_and_jsonl(tmp_path):
    note = CollectedNote(
        note_id="n1",
        note_url="https://www.xiaohongshu.com/explore/n1",
        cover_url="https://cover",
        title="艾薇岚标题",
        desc="北京描述",
        tags=["大超炮"],
        author_nickname="作者",
        author_user_id="u1",
        red_id="r1",
        publish_time=datetime(2026, 5, 18, 12, 0, 0),
        liked_count="1",
        collected_count="2",
        comment_count="3",
        share_count="4",
        matched_keywords=["艾薇岚", "北京"],
        matched_in_title=["艾薇岚"],
        matched_in_desc=["北京"],
        matched_in_tags=[],
        sources=["user", "search"],
        search_query="艾薇岚 大超炮 北京",
        crawl_time=datetime(2026, 5, 18, 13, 0, 0),
    )
    events = [
        CrawlEvent(
            level="warning",
            event_type="search_candidate_cap_reached",
            message="公开搜索达到候选上限，可能未抓全",
            channel="search",
            search_query="艾薇岚 大超炮 北京",
            count=1000,
            extra={"seen_at": datetime(2026, 5, 18, 13, 30, 0)},
        )
    ]

    result = write_outputs(
        notes=[note],
        keyword_rows=[],
        stats_rows=[{"metric": "hit_notes", "value": 1}],
        events=events,
        output_dir=str(tmp_path),
        task_name="艾薇岚大超炮北京",
        timestamp="20260518_130000",
    )

    wb = openpyxl.load_workbook(result["xlsx"])
    assert wb.sheetnames == ["命中帖子汇总", "按关键词展开明细", "采集统计", "异常与边界日志"]
    assert wb["命中帖子汇总"]["A1"].value == "note_id"
    assert wb["命中帖子汇总"]["A2"].value == "n1"
    assert cell_value_by_header(wb["命中帖子汇总"], 2, "tags") == "大超炮"
    assert (
        cell_value_by_header(wb["命中帖子汇总"], 2, "publish_time")
        == "2026-05-18 12:00:00"
    )
    assert cell_value_by_header(wb["命中帖子汇总"], 2, "detail_status") == "detail"
    assert (
        cell_value_by_header(wb["命中帖子汇总"], 2, "matched_keywords")
        == "艾薇岚，北京"
    )
    assert cell_value_by_header(wb["按关键词展开明细"], 2, "keyword") == "艾薇岚"
    assert cell_value_by_header(wb["按关键词展开明细"], 3, "keyword") == "北京"
    assert wb["异常与边界日志"]["I2"].value == '{"seen_at": "2026-05-18 13:30:00"}'

    lines = result["jsonl"].read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["note_id"] == "n1"

    log_lines = result["log_jsonl"].read_text(encoding="utf-8").splitlines()
    assert json.loads(log_lines[0])["event_type"] == "search_candidate_cap_reached"


def test_write_outputs_sanitizes_task_name_in_filenames(tmp_path):
    result = write_outputs(
        notes=[],
        keyword_rows=[],
        stats_rows=[],
        events=[],
        output_dir=str(tmp_path),
        task_name="A/B:测试",
        timestamp="20260518_130000",
    )

    for path in result.values():
        assert path.exists()
        assert "/" not in path.name
        assert ":" not in path.name
        assert "A_B_测试" in path.name


def test_write_outputs_passes_detail_index_to_dashboard(tmp_path):
    note = CollectedNote(
        note_id="n1",
        note_url="https://www.xiaohongshu.com/explore/n1",
        cover_url="https://cover",
        title="艾薇岚标题",
        desc="北京描述",
        tags=["大超炮"],
        author_nickname="作者",
        author_user_id="u1",
        red_id="r1",
        publish_time=datetime(2026, 5, 18, 12, 0, 0),
        liked_count="1",
        collected_count="2",
        comment_count="3",
        share_count="4",
        matched_keywords=["艾薇岚"],
        sources=["search"],
    )
    md_path = tmp_path / "md" / "01_n1.md"
    md_path.parent.mkdir()
    md_path.write_text("# 详情\n", encoding="utf-8")

    result = write_outputs(
        notes=[note],
        keyword_rows=[],
        stats_rows=[],
        events=[],
        output_dir=str(tmp_path),
        task_name="详情链接",
        timestamp="20260518_130000",
        detail_index={"n1": {"status": "success", "md_path": str(md_path)}},
    )

    html = result["html"].read_text(encoding="utf-8")
    assert "打开正文" in html
    assert md_path.resolve().as_uri() in html
