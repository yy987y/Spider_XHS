import json
from pathlib import Path

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
