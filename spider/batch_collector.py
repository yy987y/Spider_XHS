from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from spider.batch_account_resolver import AccountResolver
from spider.batch_aggregator import NoteAggregator
from spider.batch_matcher import match_note_keywords
from spider.batch_models import CollectTaskConfig, CollectedNote, CrawlEvent
from spider.batch_time import is_before_range, is_in_range
from xhs_utils.data_util import handle_note_info


@dataclass
class BatchCollectResult:
    notes: list[CollectedNote]
    events: list[CrawlEvent] = field(default_factory=list)
    stats_rows: list[dict] = field(default_factory=list)


class BatchNoteCollector:
    def __init__(self, api, cookies_str: str, config: CollectTaskConfig, proxies=None):
        self.api = api
        self.cookies_str = cookies_str
        self.config = config
        self.proxies = proxies
        self.events = []
        self.aggregator = NoteAggregator()

    def collect(self, red_ids: list[str]) -> BatchCollectResult:
        if self.config.run_user_channel:
            self._collect_user_channel(red_ids)
        if self.config.run_search_channel:
            self._collect_search_channel()
        notes = self.aggregator.items()
        return BatchCollectResult(
            notes=notes,
            events=self.events,
            stats_rows=self._build_stats(notes),
        )

    def _collect_user_channel(self, red_ids: list[str]) -> None:
        resolver = AccountResolver(
            api=self.api,
            cookies_str=self.cookies_str,
            cache_path=self.config.cache_path,
            proxies=self.proxies,
        )
        for red_id in red_ids:
            try:
                resolved = resolver.resolve(red_id)
            except Exception as exc:
                self._add_event(
                    level="error",
                    event_type="user_resolve_failed",
                    message=str(exc),
                    channel="user",
                    red_id=red_id,
                )
                continue
            self._collect_resolved_user(resolved)

    def _collect_resolved_user(self, resolved) -> None:
        cursor = ""
        page = 1
        while True:
            success, msg, res_json = self.api.get_user_note_info(
                resolved.user_id,
                cursor,
                self.cookies_str,
                proxies=self.proxies,
            )
            if not success:
                self._add_event(
                    level="error",
                    event_type="user_notes_page_failed",
                    message=f"指定用户帖子页拉取失败: {msg}",
                    channel="user",
                    red_id=resolved.red_id,
                    page=page,
                )
                return

            data = (res_json or {}).get("data", {})
            notes = data.get("notes") or []
            detail_times = []
            for simple_note in notes:
                note_id = simple_note.get("note_id") or simple_note.get("id")
                if not note_id:
                    continue
                xsec_token = simple_note.get("xsec_token", "")
                note_url = (
                    f"https://www.xiaohongshu.com/explore/{note_id}"
                    f"?xsec_token={xsec_token}&xsec_source=pc_user"
                )
                publish_time = self._fetch_note_detail(
                    note_url,
                    source="user",
                    red_id=resolved.red_id,
                )
                if publish_time:
                    detail_times.append(publish_time)

            if detail_times and all(
                is_before_range(publish_time, self.config.date_range)
                for publish_time in detail_times
            ):
                self._add_event(
                    level="info",
                    event_type="user_before_date_range",
                    message="指定用户通道已翻到时间范围之前，停止该用户分页",
                    channel="user",
                    red_id=resolved.red_id,
                    page=page,
                    count=len(detail_times),
                )
                return

            if not data.get("has_more"):
                return
            next_cursor = data.get("cursor")
            if not next_cursor or next_cursor == cursor:
                return
            cursor = next_cursor
            page += 1

    def _collect_search_channel(self) -> None:
        page = 1
        candidate_count = 0
        while True:
            success, msg, res_json = self.api.search_note(
                self.config.search_query,
                self.cookies_str,
                page=page,
                sort_type_choice=self.config.sort_type_choice,
                proxies=self.proxies,
            )
            if not success:
                self._add_event(
                    level="error",
                    event_type="search_page_failed",
                    message=f"公开搜索页拉取失败: {msg}",
                    channel="search",
                    search_query=self.config.search_query,
                    page=page,
                )
                return

            data = (res_json or {}).get("data", {})
            items = data.get("items") or []
            detail_times = []
            reached_cap = False
            for item in items:
                if item.get("model_type") != "note":
                    continue
                if candidate_count >= self.config.max_search_candidates:
                    reached_cap = True
                    break
                candidate_count += 1
                note_id = item.get("id") or item.get("note_id")
                if not note_id:
                    continue
                xsec_token = item.get("xsec_token", "")
                note_url = (
                    f"https://www.xiaohongshu.com/explore/{note_id}"
                    f"?xsec_token={xsec_token}&xsec_source=pc_search"
                )
                publish_time = self._fetch_note_detail(
                    note_url,
                    source="search",
                    red_id="",
                )
                if publish_time:
                    detail_times.append(publish_time)

            if reached_cap or candidate_count >= self.config.max_search_candidates:
                self._add_event(
                    level="warning",
                    event_type="search_candidate_cap_reached",
                    message="公开搜索达到候选上限，平台召回可能未抓全",
                    channel="search",
                    search_query=self.config.search_query,
                    page=page,
                    count=candidate_count,
                    extra={"platform_search_not_strictly_exhaustive": True},
                )
                return

            if detail_times and all(
                is_before_range(publish_time, self.config.date_range)
                for publish_time in detail_times
            ):
                self._add_event(
                    level="info",
                    event_type="search_before_date_range",
                    message="公开搜索已翻到时间范围之前，但平台搜索召回不保证绝对全量",
                    channel="search",
                    search_query=self.config.search_query,
                    page=page,
                    count=len(detail_times),
                    extra={"platform_search_not_strictly_exhaustive": True},
                )
                return

            if not data.get("has_more"):
                self._add_event(
                    level="info",
                    event_type="search_no_more",
                    message="公开搜索通道无更多结果，平台搜索召回不保证绝对全量",
                    channel="search",
                    search_query=self.config.search_query,
                    page=page,
                    count=candidate_count,
                    extra={"platform_search_not_strictly_exhaustive": True},
                )
                return
            page += 1

    def _fetch_note_detail(self, note_url: str, source: str, red_id: str) -> datetime | None:
        success, msg, res_json = self.api.get_note_info(
            note_url,
            self.cookies_str,
            proxies=self.proxies,
        )
        if not success:
            self._add_event(
                level="error",
                event_type="note_detail_failed",
                message=f"帖子详情拉取失败: {msg}",
                channel=source,
                red_id=red_id,
                search_query=self.config.search_query if source == "search" else "",
                extra={"note_url": note_url},
            )
            return None

        items = ((res_json or {}).get("data") or {}).get("items") or []
        if not items:
            self._add_event(
                level="warning",
                event_type="note_detail_empty",
                message="帖子详情为空",
                channel=source,
                red_id=red_id,
                search_query=self.config.search_query if source == "search" else "",
                extra={"note_url": note_url},
            )
            return None

        note_info = handle_note_info(items[0])
        publish_time = datetime.strptime(note_info["upload_time"], "%Y-%m-%d %H:%M:%S")
        if not is_in_range(publish_time, self.config.date_range):
            return publish_time

        match = match_note_keywords(
            title=note_info.get("title", ""),
            desc=note_info.get("desc", ""),
            tags=note_info.get("tags", []),
            keywords=self.config.board_keywords,
        )
        if not match.matched_keywords:
            return publish_time

        image_list = note_info.get("image_list") or [""]
        cover_url = note_info.get("video_cover") or image_list[0]
        self.aggregator.add(
            CollectedNote(
                note_id=note_info["note_id"],
                note_url=note_info["note_url"],
                cover_url=cover_url,
                title=note_info.get("title", ""),
                desc=note_info.get("desc", ""),
                tags=note_info.get("tags", []),
                author_nickname=note_info.get("nickname", ""),
                author_user_id=note_info.get("user_id", ""),
                red_id=red_id,
                publish_time=publish_time,
                liked_count=note_info.get("liked_count", ""),
                collected_count=note_info.get("collected_count", ""),
                comment_count=note_info.get("comment_count", ""),
                share_count=note_info.get("share_count", ""),
                matched_keywords=match.matched_keywords,
                matched_in_title=match.matched_in_title,
                matched_in_desc=match.matched_in_desc,
                matched_in_tags=match.matched_in_tags,
                sources=[source],
                search_query=self.config.search_query if source == "search" else "",
                raw_meta={"ip_location": note_info.get("ip_location", "")},
            )
        )
        return publish_time

    def _build_stats(self, notes: list[CollectedNote]) -> list[dict]:
        date_range = self.config.date_range
        return [
            {"metric": "total_hit_notes", "value": len(notes)},
            {"metric": "total_events", "value": len(self.events)},
            {"metric": "run_user_channel", "value": self.config.run_user_channel},
            {"metric": "run_search_channel", "value": self.config.run_search_channel},
            {"metric": "date_range", "value": date_range.label},
            {"metric": "search_query", "value": self.config.search_query},
            {
                "metric": "max_search_candidates",
                "value": self.config.max_search_candidates,
            },
        ]

    def _add_event(
        self,
        level: str,
        event_type: str,
        message: str,
        channel: str = "",
        red_id: str = "",
        search_query: str = "",
        page: int | None = None,
        count: int | None = None,
        extra: dict | None = None,
    ) -> None:
        self.events.append(
            CrawlEvent(
                level=level,
                event_type=event_type,
                message=message,
                channel=channel,
                red_id=red_id,
                search_query=search_query,
                page=page,
                count=count,
                extra=extra or {},
            )
        )
