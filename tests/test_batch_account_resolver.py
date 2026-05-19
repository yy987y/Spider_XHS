import json

import openpyxl

from spider.batch_account_resolver import AccountResolver, read_red_ids_from_excel


class FakeApi:
    def search_some_user(self, query, require_num, cookies_str, proxies=None):
        return True, "success", [
            {
                "user_info": {
                    "user_id": "u123",
                    "nickname": "测试账号",
                    "red_id": query,
                }
            }
        ]


class CurrentSearchUserShapeApi:
    def search_some_user(self, query, require_num, cookies_str, proxies=None):
        return True, "success", [
            {
                "id": "u-current",
                "name": "现网账号",
                "red_id": query,
                "xsec_token": "user-token",
            }
        ]


class ExplodingApi:
    def search_some_user(self, query, require_num, cookies_str, proxies=None):
        raise AssertionError("cache hit should not call API")


def test_read_red_ids_from_excel(tmp_path):
    path = tmp_path / "users.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["red_id"])
    ws.append(["abc123"])
    ws.append([""])
    ws.append(["def456"])
    wb.save(path)

    assert read_red_ids_from_excel(str(path)) == ["abc123", "def456"]


def test_read_red_ids_from_excel_closes_workbook(monkeypatch):
    class FakeSheet:
        def iter_rows(self, values_only=True):
            return iter([("red_id",), ("abc123",)])

    class FakeWorkbook:
        active = FakeSheet()

        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    wb = FakeWorkbook()

    def fake_load_workbook(path, read_only=True, data_only=True):
        return wb

    monkeypatch.setattr(openpyxl, "load_workbook", fake_load_workbook)

    assert read_red_ids_from_excel("users.xlsx") == ["abc123"]
    assert wb.closed is True


def test_account_resolver_resolves_and_writes_cache(tmp_path):
    cache_path = tmp_path / "cache.jsonl"
    resolver = AccountResolver(api=FakeApi(), cookies_str="cookie", cache_path=str(cache_path))

    resolved = resolver.resolve("abc123")

    assert resolved.red_id == "abc123"
    assert resolved.user_id == "u123"
    assert resolved.user_url == "https://www.xiaohongshu.com/user/profile/u123"
    assert resolved.nickname == "测试账号"
    assert resolved.source == "api"
    cached = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines()]
    assert cached[0]["red_id"] == "abc123"


def test_account_resolver_supports_current_search_user_shape(tmp_path):
    cache_path = tmp_path / "cache.jsonl"
    resolver = AccountResolver(
        api=CurrentSearchUserShapeApi(),
        cookies_str="cookie",
        cache_path=str(cache_path),
    )

    resolved = resolver.resolve("abc123")

    assert resolved.user_id == "u-current"
    assert resolved.nickname == "现网账号"
    assert resolved.raw_summary["matched_user"]["xsec_token"] == "user-token"


def test_account_resolver_uses_cache(tmp_path):
    cache_path = tmp_path / "cache.jsonl"
    cache_path.write_text(
        json.dumps(
            {
                "red_id": "abc123",
                "user_id": "u123",
                "user_url": "https://www.xiaohongshu.com/user/profile/u123",
                "nickname": "缓存账号",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    resolver = AccountResolver(api=FakeApi(), cookies_str="cookie", cache_path=str(cache_path))

    resolved = resolver.resolve("abc123")

    assert resolved.nickname == "缓存账号"
    assert resolved.source == "cache"


def test_account_resolver_skips_bad_cache_lines_and_uses_valid_cache(tmp_path):
    cache_path = tmp_path / "cache.jsonl"
    valid_item = {
        "red_id": "abc123",
        "user_id": "u123",
        "user_url": "https://www.xiaohongshu.com/user/profile/u123",
        "nickname": "有效缓存",
    }
    cache_path.write_text(
        "not-json\n"
        + json.dumps({"red_id": "missing-required-fields"}, ensure_ascii=False)
        + "\n"
        + json.dumps(valid_item, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    resolver = AccountResolver(api=ExplodingApi(), cookies_str="cookie", cache_path=str(cache_path))

    resolved = resolver.resolve("abc123")

    assert resolved.nickname == "有效缓存"
    assert resolved.source == "cache"
