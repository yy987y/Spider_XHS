from datetime import datetime

import openpyxl

from spider.batch_dashboard import build_dashboard_from_xlsx
from spider.batch_models import CollectedNote
from spider.batch_report import write_outputs


def test_build_dashboard_from_xlsx_creates_dark_sortable_html_without_modifying_xlsx(tmp_path):
    note = CollectedNote(
        note_id="n1",
        note_url="https://www.xiaohongshu.com/explore/n1",
        cover_url="https://cover",
        title="北京大超炮真实记录",
        desc="",
        tags=[],
        author_nickname="作者",
        author_user_id="u1",
        red_id="",
        publish_time=None,
        publish_time_text="1小时前",
        note_type="normal",
        liked_count="12",
        collected_count="3",
        comment_count="4",
        share_count="5",
        detail_status="search_list_only",
        matched_keywords=["大超炮", "北京"],
        matched_in_title=["大超炮", "北京"],
        sources=["search"],
        search_query="大超炮 北京",
        crawl_time=datetime(2026, 5, 18, 13, 0, 0),
    )
    outputs = write_outputs(
        notes=[note],
        keyword_rows=[],
        stats_rows=[{"metric": "total_hit_notes", "value": 1}],
        events=[],
        output_dir=str(tmp_path),
        task_name="大超炮北京",
        timestamp="20260518_130000",
    )
    before_size = outputs["xlsx"].stat().st_size
    before_sheets = openpyxl.load_workbook(outputs["xlsx"], read_only=True).sheetnames

    html_path = build_dashboard_from_xlsx(outputs["xlsx"])

    assert outputs["xlsx"].stat().st_size == before_size
    assert openpyxl.load_workbook(outputs["xlsx"], read_only=True).sheetnames == before_sheets
    html = html_path.read_text(encoding="utf-8")
    assert "北京大超炮真实记录" in html
    assert 'id="notes" class="note-list"' in html
    assert 'class="list-row"' in html
    assert 'class="grid"' not in html
    assert 'class="card"' not in html
    assert "data-sort-key=\"liked_count\"" in html
    assert "data-sort-key=\"comment_count\"" in html
    assert "data-sort-key=\"share_count\"" in html
    assert "data-sort-key=\"collected_count\"" in html
    assert "background: #0b0f17" in html


def test_build_dashboard_from_xlsx_adds_detail_markdown_links(tmp_path):
    note = CollectedNote(
        note_id="n1",
        note_url="https://www.xiaohongshu.com/explore/n1",
        cover_url="https://cover",
        title="北京大超炮真实记录",
        desc="",
        tags=[],
        author_nickname="作者",
        author_user_id="u1",
        red_id="",
        publish_time=None,
        publish_time_text="1小时前",
        note_type="normal",
        liked_count="12",
        collected_count="3",
        comment_count="4",
        share_count="5",
        detail_status="search_list_only",
        matched_keywords=["大超炮", "北京"],
        matched_in_title=["大超炮", "北京"],
        sources=["search"],
        search_query="大超炮 北京",
        crawl_time=datetime(2026, 5, 18, 13, 0, 0),
    )
    outputs = write_outputs(
        notes=[note],
        keyword_rows=[],
        stats_rows=[{"metric": "total_hit_notes", "value": 1}],
        events=[],
        output_dir=str(tmp_path),
        task_name="大超炮北京",
        timestamp="20260518_130000",
    )
    md_path = tmp_path / "details" / "01_n1.md"
    md_path.parent.mkdir()
    md_path.write_text("# 详情正文\n", encoding="utf-8")
    detail_index = {"n1": {"status": "success", "md_path": str(md_path)}}

    html_path = build_dashboard_from_xlsx(outputs["xlsx"], detail_index=detail_index)

    html = html_path.read_text(encoding="utf-8")
    assert "打开正文" in html
    assert md_path.resolve().as_uri() in html
    assert "detail_status" in html
