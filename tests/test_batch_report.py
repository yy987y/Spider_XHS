import json
from datetime import datetime

import openpyxl

from spider.batch_models import CollectedNote, CrawlEvent
from spider.batch_report import write_outputs


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
    assert wb["命中帖子汇总"]["F2"].value == "大超炮"
    assert wb["命中帖子汇总"]["J2"].value == "2026-05-18 12:00:00"
    assert wb["命中帖子汇总"]["O2"].value == "艾薇岚，北京"
    assert wb["按关键词展开明细"]["V2"].value == "艾薇岚"
    assert wb["按关键词展开明细"]["V3"].value == "北京"
    assert wb["异常与边界日志"]["I2"].value == '{"seen_at": "2026-05-18 13:30:00"}'

    lines = result["jsonl"].read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["note_id"] == "n1"

    log_lines = result["log_jsonl"].read_text(encoding="utf-8").splitlines()
    assert json.loads(log_lines[0])["event_type"] == "search_candidate_cap_reached"
