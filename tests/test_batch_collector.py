from datetime import datetime

from spider.batch_collector import BatchNoteCollector
from spider.batch_models import CollectTaskConfig
from spider.batch_time import parse_date_range


class FakeApi:
    def search_some_user(self, query, require_num, cookies_str, proxies=None):
        return True, "success", [
            {"user_info": {"user_id": "u1", "red_id": query, "nickname": "账号1"}}
        ]

    def get_user_note_info(
        self,
        user_id,
        cursor,
        cookies_str,
        xsec_token="",
        xsec_source="",
        proxies=None,
    ):
        if cursor:
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {"notes": [], "has_more": False},
            }
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "notes": [{"note_id": "n1", "xsec_token": "token1"}],
                "cursor": "next",
                "has_more": False,
            },
        }

    def search_note(
        self,
        query,
        cookies_str,
        page=1,
        sort_type_choice=0,
        note_type=0,
        note_time=0,
        note_range=0,
        pos_distance=0,
        geo="",
        search_id=None,
        proxies=None,
    ):
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [{"model_type": "note", "id": "n1", "xsec_token": "token1"}],
                "has_more": False,
            },
        }

    def get_note_info(self, url, cookies_str, proxies=None):
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [
                    {
                        "id": "n1",
                        "url": url,
                        "note_card": {
                            "type": "normal",
                            "user": {
                                "user_id": "u1",
                                "nickname": "账号1",
                                "avatar": "https://avatar",
                            },
                            "title": "艾薇岚大超炮北京体验",
                            "desc": "正文描述",
                            "interact_info": {
                                "liked_count": "10",
                                "collected_count": "2",
                                "comment_count": "3",
                                "share_count": "1",
                            },
                            "image_list": [{"info_list": [{}, {"url": "https://cover"}]}],
                            "tag_list": [{"name": "北京"}],
                            "time": 1779091200000,
                            "ip_location": "北京",
                        },
                    }
                ]
            },
        }


def test_batch_collector_collects_user_and_search_channels(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        cache_path=str(tmp_path / "cache.jsonl"),
        max_search_candidates=10,
    )
    collector = BatchNoteCollector(api=FakeApi(), cookies_str="cookie", config=config)

    result = collector.collect(red_ids=["red1"])

    assert len(result.notes) == 1
    assert result.notes[0].note_id == "n1"
    assert result.notes[0].cover_url == "https://cover"
    assert result.notes[0].sources == ["user", "search"]
    assert result.notes[0].matched_keywords == ["艾薇岚", "大超炮", "北京"]


def test_batch_collector_logs_search_candidate_cap(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        run_user_channel=False,
        cache_path=str(tmp_path / "cache.jsonl"),
        max_search_candidates=1,
    )
    collector = BatchNoteCollector(api=FakeApi(), cookies_str="cookie", config=config)

    result = collector.collect(red_ids=[])

    assert len(result.notes) == 1
    assert any(
        event.event_type == "search_candidate_cap_reached" and event.level == "warning"
        for event in result.events
    )
