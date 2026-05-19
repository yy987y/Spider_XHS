import json
from datetime import datetime

from spider.batch_models import CollectedNote
from spider.cdp_note_exporter import _cookies_from_string, _encode_cdp_url, export_note_details


class FakeCdpClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.opened_urls = []
        self.closed = False

    def ensure_ready(self):
        return None

    def extract_note(self, url):
        self.opened_urls.append(url)
        payload = self.payloads[url]
        if isinstance(payload, Exception):
            raise payload
        return payload

    def close(self):
        self.closed = True


def make_note(note_id, url):
    return CollectedNote(
        note_id=note_id,
        note_url=url,
        cover_url="https://cover",
        title="列表标题",
        desc="",
        tags=[],
        author_nickname="列表作者",
        author_user_id="list-user",
        red_id="",
        publish_time=None,
        liked_count="1",
        collected_count="2",
        comment_count="3",
        share_count="4",
        matched_keywords=["关键词"],
        sources=["search"],
        search_query="关键词",
        crawl_time=datetime(2026, 5, 18, 12, 0, 0),
    )


def test_export_note_details_writes_markdown_jsonl_and_summary(tmp_path):
    good_url = "https://www.xiaohongshu.com/explore/n1?xsec_token=t"
    bad_url = "https://www.xiaohongshu.com/explore/n2?xsec_token=t"
    client = FakeCdpClient(
        {
            good_url: {
                "pageUrl": good_url,
                "noteId": "n1",
                "note": {
                    "noteId": "n1",
                    "title": "CDP 标题",
                    "desc": "CDP 正文",
                    "type": "normal",
                    "time": 1779091200000,
                    "ipLocation": "北京",
                    "user": {"nickname": "作者", "userId": "u1"},
                    "tags": ["标签A"],
                    "interact": {
                        "likedCount": "10",
                        "collectedCount": "5",
                        "commentCount": "2",
                        "shareCount": "1",
                    },
                    "images": ["https://image-1"],
                },
                "comments": [
                    {
                        "content": "评论内容",
                        "createTime": 1779091300000,
                        "ipLocation": "上海",
                        "likeCount": "7",
                        "user": {"nickname": "评论者", "userId": "c1"},
                    }
                ],
            },
            bad_url: RuntimeError("登录态失效"),
        }
    )

    result = export_note_details(
        notes=[make_note("n1", good_url), make_note("n2", bad_url)],
        output_dir=tmp_path,
        task_name="测试任务",
        cdp_client=client,
        timestamp="20260518_130000",
    )

    assert client.opened_urls == [good_url, bad_url]
    assert client.closed is True
    assert result["md_dir"].exists()
    assert result["jsonl"].exists()
    assert result["summary"].exists()

    md_text = (result["md_dir"] / "01_n1.md").read_text(encoding="utf-8")
    assert "# CDP 标题" in md_text
    assert "CDP 正文" in md_text
    assert "![图片1](https://image-1)" in md_text
    assert "评论者：评论内容" in md_text

    detail_rows = [
        json.loads(line)
        for line in result["jsonl"].read_text(encoding="utf-8").splitlines()
    ]
    assert [row["status"] for row in detail_rows] == ["success", "error"]
    assert detail_rows[0]["md_path"].endswith("01_n1.md")
    assert detail_rows[1]["error"] == "RuntimeError: 登录态失效"

    summary = json.loads(result["summary"].read_text(encoding="utf-8"))
    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["md_dir"] == str(result["md_dir"])


def test_encode_cdp_url_preserves_path_but_escapes_query_separators():
    encoded = _encode_cdp_url(
        "https://www.xiaohongshu.com/explore/n1?xsec_token=a&xsec_source=pc_search"
    )

    assert encoded.startswith("https://www.xiaohongshu.com/explore/n1")
    assert "%3F" in encoded
    assert "%26" in encoded


def test_cookies_from_string_parses_login_cookie_values_with_equals():
    cookies = _cookies_from_string("a1=abc; web_session=session==; webId=wid")

    assert cookies == {
        "a1": "abc",
        "web_session": "session==",
        "webId": "wid",
    }
