from datetime import datetime

from spider.batch_collector import BatchNoteCollector
from spider.batch_models import CollectTaskConfig
from spider.batch_time import parse_date_range


class FakeApi:
    def __init__(self):
        self.resolved_queries = []
        self.detail_urls = []
        self.search_pages = []
        self.search_ids = []

    def search_some_user(self, query, require_num, cookies_str, proxies=None):
        self.resolved_queries.append(query)
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
                "notes": [
                    {"note_id": "n1", "xsec_token": "token1"},
                    {"note_id": "n2", "xsec_token": "token2"},
                    {"note_id": "n3", "xsec_token": "token3"},
                ],
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
        self.search_pages.append(page)
        self.search_ids.append(search_id)
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [{"model_type": "note", "id": "n1", "xsec_token": "token1"}],
                "has_more": False,
            },
        }

    def get_note_info(self, url, cookies_str, proxies=None):
        self.detail_urls.append(url)
        note_id = url.split("/explore/", 1)[1].split("?", 1)[0]
        note_payloads = {
            "n1": {
                "title": "艾薇岚大超炮北京体验",
                "desc": "正文描述",
                "tags": [{"name": "北京"}],
                "time": 1779091200000,
            },
            "n2": {
                "title": "无关标题",
                "desc": "普通正文",
                "tags": [{"name": "上海"}],
                "time": 1779091200000,
            },
            "n3": {
                "title": "艾薇岚大超炮北京旧帖",
                "desc": "正文描述",
                "tags": [{"name": "北京"}],
                "time": 1700000000000,
            },
            "n4": {
                "title": "艾薇岚大超炮北京第二篇",
                "desc": "正文描述",
                "tags": [{"name": "北京"}],
                "time": 1779091200000,
            },
        }
        note_payload = note_payloads[note_id]
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [
                    {
                        "id": note_id,
                        "url": url,
                        "note_card": {
                            "type": "normal",
                            "user": {
                                "user_id": "u1",
                                "nickname": "账号1",
                                "avatar": "https://avatar",
                            },
                            "title": note_payload["title"],
                            "desc": note_payload["desc"],
                            "interact_info": {
                                "liked_count": "10",
                                "collected_count": "2",
                                "comment_count": "3",
                                "share_count": "1",
                            },
                            "image_list": [{"info_list": [{}, {"url": "https://cover"}]}],
                            "tag_list": note_payload["tags"],
                            "time": note_payload["time"],
                            "ip_location": "北京",
                        },
                    }
                ]
            },
        }


class SearchCapFakeApi(FakeApi):
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
        self.search_pages.append(page)
        self.search_ids.append(search_id)
        if page == 1:
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {
                    "items": [
                        {"model_type": "user", "id": "u-skip", "xsec_token": "skip"},
                        {"model_type": "note", "id": "n1", "xsec_token": "token1"},
                        {"model_type": "note", "id": "n4", "xsec_token": "token4"},
                    ],
                    "has_more": True,
                },
            }
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [{"model_type": "note", "id": "n4", "xsec_token": "token4"}],
                "has_more": False,
            },
        }


class ParseErrorFakeApi(FakeApi):
    def get_user_note_info(
        self,
        user_id,
        cursor,
        cookies_str,
        xsec_token="",
        xsec_source="",
        proxies=None,
    ):
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "notes": [
                    {"note_id": "bad", "xsec_token": "bad-token"},
                    {"note_id": "bad_attr", "xsec_token": "bad-attr-token"},
                    {"note_id": "n1", "xsec_token": "token1"},
                ],
                "has_more": False,
            },
        }

    def get_note_info(self, url, cookies_str, proxies=None):
        self.detail_urls.append(url)
        note_id = url.split("/explore/", 1)[1].split("?", 1)[0]
        if note_id == "bad":
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {"items": [{"id": "bad", "url": url, "note_card": {}}]},
            }
        if note_id == "bad_attr":
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {
                    "items": [
                        {
                            "id": "bad_attr",
                            "url": url,
                            "note_card": {
                                "type": "normal",
                                "user": {
                                    "user_id": "u1",
                                    "nickname": "账号1",
                                    "avatar": "https://avatar",
                                },
                                "title": None,
                                "desc": "正文描述",
                                "interact_info": {
                                    "liked_count": "10",
                                    "collected_count": "2",
                                    "comment_count": "3",
                                    "share_count": "1",
                                },
                                "image_list": [
                                    {"info_list": [{}, {"url": "https://cover"}]}
                                ],
                                "tag_list": [{"name": "北京"}],
                                "time": 1779091200000,
                                "ip_location": "北京",
                            },
                        }
                    ]
                },
            }
        return super().get_note_info(url, cookies_str, proxies)


class BadListShapeFakeApi(FakeApi):
    def get_user_note_info(
        self,
        user_id,
        cursor,
        cookies_str,
        xsec_token="",
        xsec_source="",
        proxies=None,
    ):
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "notes": [
                    None,
                    "bad-note",
                    {"note_id": "n1", "xsec_token": "token1"},
                ],
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
        self.search_pages.append(page)
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [
                    None,
                    "bad-item",
                    {"model_type": "note", "id": "n1", "xsec_token": "token1"},
                ],
                "has_more": False,
            },
        }


class EmptyDataFakeApi(FakeApi):
    def get_user_note_info(
        self,
        user_id,
        cursor,
        cookies_str,
        xsec_token="",
        xsec_source="",
        proxies=None,
    ):
        return True, "success", {"success": True, "msg": "success", "data": None}

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
        self.search_pages.append(page)
        self.search_ids.append(search_id)
        return True, "success", {"success": True, "msg": "success", "data": None}


class MultiPageSearchFakeApi(FakeApi):
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
        self.search_pages.append(page)
        self.search_ids.append(search_id)
        if page == 1:
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {
                    "items": [{"model_type": "note", "id": "n1", "xsec_token": "token1"}],
                    "has_more": True,
                },
            }
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [{"model_type": "note", "id": "n4", "xsec_token": "token4"}],
                "has_more": False,
            },
        }


class SearchListCardFakeApi(FakeApi):
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
        self.search_pages.append(page)
        self.search_ids.append(search_id)
        self.note_time = note_time
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "items": [
                    {
                        "model_type": "note",
                        "id": "n-search",
                        "xsec_token": "search-token",
                        "note_card": {
                            "type": "normal",
                            "display_title": "北京大超炮真实记录",
                            "corner_tag_info": [
                                {"type": "publish_time", "text": "1小时前"}
                            ],
                            "user": {
                                "user_id": "author-1",
                                "nickname": "搜索作者",
                            },
                            "interact_info": {
                                "liked_count": "12",
                                "collected_count": "3",
                                "comment_count": "4",
                                "shared_count": "5",
                            },
                            "cover": {"url_default": "https://cover-search"},
                        },
                    }
                ],
                "has_more": False,
            },
        }

    def get_note_info(self, url, cookies_str, proxies=None):
        raise AssertionError("search list card should not fetch note detail")


class FailedDetailWithOldThenNewFakeApi(FakeApi):
    def get_user_note_info(
        self,
        user_id,
        cursor,
        cookies_str,
        xsec_token="",
        xsec_source="",
        proxies=None,
    ):
        if cursor == "next":
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {
                    "notes": [{"note_id": "n1", "xsec_token": "token1"}],
                    "has_more": False,
                },
            }
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "notes": [
                    {"note_id": "missing", "xsec_token": "missing-token"},
                    {"note_id": "n3", "xsec_token": "token3"},
                ],
                "cursor": "next",
                "has_more": True,
            },
        }

    def get_note_info(self, url, cookies_str, proxies=None):
        self.detail_urls.append(url)
        note_id = url.split("/explore/", 1)[1].split("?", 1)[0]
        if note_id == "missing":
            return False, "detail missing", {}
        return super().get_note_info(url, cookies_str, proxies)


class MalformedDetailPayloadFakeApi(FakeApi):
    def get_user_note_info(
        self,
        user_id,
        cursor,
        cookies_str,
        xsec_token="",
        xsec_source="",
        proxies=None,
    ):
        return True, "success", {
            "success": True,
            "msg": "success",
            "data": {
                "notes": [
                    {"note_id": "bad_data_list", "xsec_token": "bad-data-token"},
                    {"note_id": "bad_items_dict", "xsec_token": "bad-items-token"},
                    {"note_id": "n1", "xsec_token": "token1"},
                ],
                "has_more": False,
            },
        }

    def get_note_info(self, url, cookies_str, proxies=None):
        self.detail_urls.append(url)
        note_id = url.split("/explore/", 1)[1].split("?", 1)[0]
        if note_id == "bad_data_list":
            return True, "success", {"success": True, "msg": "success", "data": []}
        if note_id == "bad_items_dict":
            return True, "success", {
                "success": True,
                "msg": "success",
                "data": {"items": {}},
            }
        return super().get_note_info(url, cookies_str, proxies)


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
        use_note_detail_api=True,
    )
    api = FakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=["red1"])

    assert len(result.notes) == 1
    assert result.notes[0].note_id == "n1"
    assert result.notes[0].red_id == "red1"
    assert result.notes[0].cover_url == "https://cover"
    assert result.notes[0].sources == ["user", "search"]
    assert result.notes[0].matched_keywords == ["艾薇岚", "大超炮", "北京"]
    assert api.resolved_queries == ["red1"]
    assert (
        "https://www.xiaohongshu.com/explore/n1?xsec_token=token1&xsec_source=pc_user"
        in api.detail_urls
    )
    assert [note.note_id for note in result.notes] == ["n1"]


def test_batch_collector_default_disables_detail_api_for_user_channel(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        run_search_channel=False,
        cache_path=str(tmp_path / "cache.jsonl"),
    )
    api = FakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=["red1"])

    assert result.notes == []
    assert api.resolved_queries == []
    assert api.detail_urls == []
    assert any(
        event.event_type == "user_channel_disabled_without_detail_api"
        and event.level == "warning"
        for event in result.events
    )


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
    api = SearchCapFakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=[])

    assert result.notes == []
    assert api.search_pages == [1]
    assert api.detail_urls == []
    assert any(
        event.event_type == "search_item_missing_list_card" and event.level == "warning"
        for event in result.events
    )
    assert any(
        event.event_type == "search_candidate_cap_reached" and event.level == "warning"
        for event in result.events
    )


def test_batch_collector_reuses_search_id_across_pages(tmp_path):
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
        max_search_candidates=10,
    )
    api = MultiPageSearchFakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=[])

    assert result.notes == []
    assert api.search_pages == [1, 2]
    assert api.detail_urls == []
    assert len(api.search_ids) == 2
    assert all(search_id is not None for search_id in api.search_ids)
    assert len(set(api.search_ids)) == 1


def test_batch_collector_exports_search_list_card_without_detail_fetch(tmp_path):
    config = CollectTaskConfig(
        task_name="大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="大超炮 北京",
        board_keywords=["大超炮", "北京"],
        date_range=parse_date_range(
            "recent_7_days", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        run_user_channel=False,
        cache_path=str(tmp_path / "cache.jsonl"),
        max_search_candidates=10,
        search_note_time_choice=2,
    )
    api = SearchListCardFakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=[])

    assert api.note_time == 2
    assert [note.note_id for note in result.notes] == ["n-search"]
    assert result.notes[0].title == "北京大超炮真实记录"
    assert result.notes[0].publish_time is None
    assert result.notes[0].publish_time_text == "1小时前"
    assert result.notes[0].note_type == "normal"
    assert result.notes[0].detail_status == "search_list_only"
    assert result.notes[0].liked_count == "12"
    assert result.notes[0].collected_count == "3"
    assert result.notes[0].comment_count == "4"
    assert result.notes[0].share_count == "5"
    assert result.notes[0].cover_url == "https://cover-search"
    assert result.notes[0].matched_keywords == ["大超炮", "北京"]
    assert result.notes[0].sources == ["search"]


def test_batch_collector_skips_parse_failed_detail_and_continues(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        run_search_channel=False,
        cache_path=str(tmp_path / "cache.jsonl"),
        use_note_detail_api=True,
    )
    collector = BatchNoteCollector(
        api=ParseErrorFakeApi(), cookies_str="cookie", config=config
    )

    result = collector.collect(red_ids=["red1"])

    assert [note.note_id for note in result.notes] == ["n1"]
    assert [
        event.event_type for event in result.events
    ].count("note_detail_parse_failed") == 2


def test_batch_collector_skips_bad_list_items_and_handles_empty_data(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        cache_path=str(tmp_path / "cache.jsonl"),
        use_note_detail_api=True,
    )
    bad_list_result = BatchNoteCollector(
        api=BadListShapeFakeApi(), cookies_str="cookie", config=config
    ).collect(red_ids=["red1"])
    empty_data_result = BatchNoteCollector(
        api=EmptyDataFakeApi(), cookies_str="cookie", config=config
    ).collect(red_ids=["red1"])

    assert [note.note_id for note in bad_list_result.notes] == ["n1"]
    assert any(
        event.event_type == "user_note_item_invalid"
        for event in bad_list_result.events
    )
    assert any(
        event.event_type == "search_item_invalid" for event in bad_list_result.events
    )
    assert empty_data_result.notes == []
    assert any(
        event.event_type == "user_page_bad_data" and event.level == "warning"
        for event in empty_data_result.events
    )
    assert any(
        event.event_type == "search_page_bad_data" and event.level == "warning"
        for event in empty_data_result.events
    )
    assert any(
        event.event_type == "search_no_more" for event in empty_data_result.events
    )


def test_batch_collector_does_not_stop_before_range_when_detail_time_unknown(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        run_search_channel=False,
        cache_path=str(tmp_path / "cache.jsonl"),
        use_note_detail_api=True,
    )
    api = FailedDetailWithOldThenNewFakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=["red1"])

    assert [note.note_id for note in result.notes] == ["n1"]
    assert any("/explore/n1?" in url for url in api.detail_urls)
    assert not any(
        event.event_type == "user_before_date_range" for event in result.events
    )


def test_batch_collector_skips_malformed_detail_payloads_and_continues(tmp_path):
    config = CollectTaskConfig(
        task_name="艾薇岚大超炮北京",
        user_excel_path="unused.xlsx",
        search_query="艾薇岚 大超炮 北京",
        board_keywords=["艾薇岚", "大超炮", "北京"],
        date_range=parse_date_range(
            "2026-05-18:2026-05-18", now=datetime(2026, 5, 18, 12, 0, 0)
        ),
        run_search_channel=False,
        cache_path=str(tmp_path / "cache.jsonl"),
        use_note_detail_api=True,
    )
    api = MalformedDetailPayloadFakeApi()
    collector = BatchNoteCollector(api=api, cookies_str="cookie", config=config)

    result = collector.collect(red_ids=["red1"])

    assert [note.note_id for note in result.notes] == ["n1"]
    assert [
        event.event_type for event in result.events
    ].count("note_detail_bad_data") == 2
