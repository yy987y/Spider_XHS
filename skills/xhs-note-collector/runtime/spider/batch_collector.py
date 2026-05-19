from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from spider.batch_account_resolver import AccountResolver
from spider.batch_aggregator import NoteAggregator
from spider.batch_matcher import match_note_keywords
from spider.batch_models import CollectTaskConfig, CollectedNote, CrawlEvent
from spider.batch_time import is_before_range, is_in_range
from xhs_utils.data_util import handle_note_info
from xhs_utils.xhs_util import generate_search_id


@dataclass
class BatchCollectResult:
    notes: list[CollectedNote]
    events: list[CrawlEvent] = field(default_factory=list)
    stats_rows: list[dict] = field(default_factory=list)


@dataclass
class _FetchDetailResult:
    publish_time: datetime | None = None
    time_confirmed: bool = False


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
            if self.config.use_note_detail_api:
                self._collect_user_channel(red_ids)
            else:
                self._add_event(
                    level="warning",
                    event_type="user_channel_disabled_without_detail_api",
                    message="指定用户通道依赖帖子详情接口；当前已为稳定性禁用",
                    channel="user",
                    count=len(red_ids),
                )
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

            raw_data = (res_json or {}).get("data")
            if not isinstance(raw_data, dict):
                self._add_event(
                    level="warning",
                    event_type="user_page_bad_data",
                    message="指定用户通道返回的 data 不是对象，已按空页处理",
                    channel="user",
                    red_id=resolved.red_id,
                    page=page,
                    extra={"data_type": type(raw_data).__name__},
                )
            data = raw_data if isinstance(raw_data, dict) else {}
            notes = data.get("notes") or []
            page_results = []
            for simple_note in notes:
                if not isinstance(simple_note, dict):
                    self._add_event(
                        level="warning",
                        event_type="user_note_item_invalid",
                        message="指定用户通道返回了非对象帖子条目，已跳过",
                        channel="user",
                        red_id=resolved.red_id,
                        page=page,
                        extra={"item_type": type(simple_note).__name__},
                    )
                    continue
                note_id = simple_note.get("note_id") or simple_note.get("id")
                if not note_id:
                    self._add_event(
                        level="warning",
                        event_type="user_note_item_invalid",
                        message="指定用户通道返回的帖子条目缺少 note_id，已跳过",
                        channel="user",
                        red_id=resolved.red_id,
                        page=page,
                        extra={"item": simple_note},
                    )
                    continue
                xsec_token = simple_note.get("xsec_token", "")
                note_url = (
                    f"https://www.xiaohongshu.com/explore/{note_id}"
                    f"?xsec_token={xsec_token}&xsec_source=pc_user"
                )
                detail_result = self._fetch_note_detail(
                    note_url,
                    source="user",
                    red_id=resolved.red_id,
                )
                page_results.append(detail_result)

            if page_results and all(
                result.time_confirmed and result.publish_time
                for result in page_results
            ) and all(
                is_before_range(result.publish_time, self.config.date_range)
                for result in page_results
            ):
                self._add_event(
                    level="info",
                    event_type="user_before_date_range",
                    message="指定用户通道已翻到时间范围之前，停止该用户分页",
                    channel="user",
                    red_id=resolved.red_id,
                    page=page,
                    count=len(page_results),
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
        root_search_id = generate_search_id()
        while True:
            search_id = generate_search_id(root_search_id)
            success, msg, res_json = self.api.search_note(
                self.config.search_query,
                self.cookies_str,
                page=page,
                sort_type_choice=self.config.sort_type_choice,
                note_time=self.config.search_note_time_choice,
                search_id=search_id,
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

            raw_data = (res_json or {}).get("data")
            if not isinstance(raw_data, dict):
                self._add_event(
                    level="warning",
                    event_type="search_page_bad_data",
                    message="公开搜索返回的 data 不是对象，已按空页处理",
                    channel="search",
                    search_query=self.config.search_query,
                    page=page,
                    extra={"data_type": type(raw_data).__name__},
                )
            data = raw_data if isinstance(raw_data, dict) else {}
            items = data.get("items") or []
            page_results = []
            reached_cap = False
            for item in items:
                if not isinstance(item, dict):
                    self._add_event(
                        level="warning",
                        event_type="search_item_invalid",
                        message="公开搜索返回了非对象条目，已跳过",
                        channel="search",
                        search_query=self.config.search_query,
                        page=page,
                        extra={"item_type": type(item).__name__},
                    )
                    continue
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
                list_result = self._add_search_list_note(
                    item=item,
                    note_id=note_id,
                    note_url=note_url,
                )
                if list_result:
                    page_results.append(list_result)
                    continue
                if not self.config.use_note_detail_api:
                    self._add_event(
                        level="warning",
                        event_type="search_item_missing_list_card",
                        message="公开搜索条目缺少可用列表信息，已跳过以避免触发详情接口频控",
                        channel="search",
                        search_query=self.config.search_query,
                        page=page,
                        extra={"note_id": note_id, "note_url": note_url},
                    )
                    page_results.append(_FetchDetailResult(time_confirmed=False))
                    continue
                detail_result = self._fetch_note_detail(
                    note_url,
                    source="search",
                    red_id="",
                )
                page_results.append(detail_result)

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

            if page_results and all(
                result.time_confirmed and result.publish_time
                for result in page_results
            ) and all(
                is_before_range(result.publish_time, self.config.date_range)
                for result in page_results
            ):
                self._add_event(
                    level="info",
                    event_type="search_before_date_range",
                    message="公开搜索已翻到时间范围之前，但平台搜索召回不保证绝对全量",
                    channel="search",
                    search_query=self.config.search_query,
                    page=page,
                    count=len(page_results),
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

    def _fetch_note_detail(
        self, note_url: str, source: str, red_id: str
    ) -> _FetchDetailResult:
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
            return _FetchDetailResult()

        if not isinstance(res_json, dict):
            self._add_note_detail_bad_data_event(
                note_url=note_url,
                source=source,
                red_id=red_id,
                message="帖子详情响应不是对象",
                extra={"response_type": type(res_json).__name__},
            )
            return _FetchDetailResult()
        data = res_json.get("data")
        if not isinstance(data, dict):
            self._add_note_detail_bad_data_event(
                note_url=note_url,
                source=source,
                red_id=red_id,
                message="帖子详情 data 不是对象",
                extra={"data_type": type(data).__name__},
            )
            return _FetchDetailResult()
        items = data.get("items")
        if not isinstance(items, list):
            self._add_note_detail_bad_data_event(
                note_url=note_url,
                source=source,
                red_id=red_id,
                message="帖子详情 items 不是列表",
                extra={"items_type": type(items).__name__},
            )
            return _FetchDetailResult()
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
            return _FetchDetailResult()
        if not isinstance(items[0], dict):
            self._add_event(
                level="warning",
                event_type="note_detail_item_invalid",
                message="帖子详情返回了非对象条目",
                channel=source,
                red_id=red_id,
                search_query=self.config.search_query if source == "search" else "",
                extra={"note_url": note_url, "item_type": type(items[0]).__name__},
            )
            return _FetchDetailResult()

        try:
            note_info = handle_note_info(items[0])
            publish_time = datetime.strptime(
                note_info["upload_time"], "%Y-%m-%d %H:%M:%S"
            )
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            self._add_event(
                level="error",
                event_type="note_detail_parse_failed",
                message=f"帖子详情解析失败: {exc}",
                channel=source,
                red_id=red_id,
                search_query=self.config.search_query if source == "search" else "",
                extra={"note_url": note_url},
            )
            return _FetchDetailResult()

        if not is_in_range(publish_time, self.config.date_range):
            return _FetchDetailResult(publish_time=publish_time, time_confirmed=True)

        match = match_note_keywords(
            title=note_info.get("title", ""),
            desc=note_info.get("desc", ""),
            tags=note_info.get("tags", []),
            keywords=self.config.board_keywords,
        )
        if not match.matched_keywords:
            return _FetchDetailResult(publish_time=publish_time, time_confirmed=True)

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
                note_type=note_info.get("note_type", ""),
                detail_status="detail",
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
        return _FetchDetailResult(publish_time=publish_time, time_confirmed=True)

    def _add_search_list_note(
        self, item: dict, note_id: str, note_url: str
    ) -> _FetchDetailResult | None:
        note_card = item.get("note_card")
        if not isinstance(note_card, dict):
            return None
        title = note_card.get("display_title") or note_card.get("title") or ""
        desc = note_card.get("desc") or ""
        tags = self._extract_search_list_tags(note_card)
        match = match_note_keywords(
            title=title,
            desc=desc,
            tags=tags,
            keywords=self.config.board_keywords,
        )
        if not match.matched_keywords:
            return _FetchDetailResult(time_confirmed=False)
        user = note_card.get("user") if isinstance(note_card.get("user"), dict) else {}
        interact = (
            note_card.get("interact_info")
            if isinstance(note_card.get("interact_info"), dict)
            else {}
        )
        self.aggregator.add(
            CollectedNote(
                note_id=note_id,
                note_url=note_url,
                cover_url=self._extract_search_list_cover(note_card),
                title=title,
                desc=desc,
                tags=tags,
                author_nickname=user.get("nickname") or user.get("nick_name") or "",
                author_user_id=user.get("user_id", ""),
                red_id="",
                publish_time=None,
                publish_time_text=self._extract_search_list_publish_text(note_card),
                note_type=note_card.get("type", ""),
                detail_status="search_list_only",
                liked_count=interact.get("liked_count", ""),
                collected_count=interact.get("collected_count", ""),
                comment_count=interact.get("comment_count", ""),
                share_count=interact.get("share_count")
                or interact.get("shared_count", ""),
                matched_keywords=match.matched_keywords,
                matched_in_title=match.matched_in_title,
                matched_in_desc=match.matched_in_desc,
                matched_in_tags=match.matched_in_tags,
                sources=["search"],
                search_query=self.config.search_query,
                raw_meta={"xsec_token": item.get("xsec_token", "")},
            )
        )
        return _FetchDetailResult(time_confirmed=False)

    @staticmethod
    def _extract_search_list_cover(note_card: dict) -> str:
        cover = note_card.get("cover") if isinstance(note_card.get("cover"), dict) else {}
        if cover.get("url_default"):
            return cover["url_default"]
        image_list = note_card.get("image_list") or []
        for image in image_list:
            if not isinstance(image, dict):
                continue
            info_list = image.get("info_list") or []
            for info in reversed(info_list):
                if isinstance(info, dict) and info.get("url"):
                    return info["url"]
        return ""

    @staticmethod
    def _extract_search_list_publish_text(note_card: dict) -> str:
        for tag in note_card.get("corner_tag_info") or []:
            if isinstance(tag, dict) and tag.get("type") == "publish_time":
                return tag.get("text", "")
        return ""

    @staticmethod
    def _extract_search_list_tags(note_card: dict) -> list[str]:
        tags = []
        for tag in note_card.get("tag_list") or []:
            if isinstance(tag, dict) and tag.get("name"):
                tags.append(tag["name"])
        return tags

    def _add_note_detail_bad_data_event(
        self,
        note_url: str,
        source: str,
        red_id: str,
        message: str,
        extra: dict,
    ) -> None:
        event_extra = {"note_url": note_url}
        event_extra.update(extra)
        self._add_event(
            level="warning",
            event_type="note_detail_bad_data",
            message=message,
            channel=source,
            red_id=red_id,
            search_query=self.config.search_query if source == "search" else "",
            extra=event_extra,
        )

    def _build_stats(self, notes: list[CollectedNote]) -> list[dict]:
        date_range = self.config.date_range
        return [
            {"metric": "total_hit_notes", "value": len(notes)},
            {"metric": "total_events", "value": len(self.events)},
            {"metric": "run_user_channel", "value": self.config.run_user_channel},
            {"metric": "run_search_channel", "value": self.config.run_search_channel},
            {"metric": "use_note_detail_api", "value": self.config.use_note_detail_api},
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
