from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_MAX_SEARCH_CANDIDATES = 50


@dataclass
class DateRange:
    start: datetime
    end: datetime
    label: str


@dataclass
class CollectTaskConfig:
    task_name: str
    user_excel_path: str
    search_query: str
    board_keywords: List[str]
    date_range: DateRange
    run_user_channel: bool = True
    run_search_channel: bool = True
    use_note_detail_api: bool = False
    max_search_candidates: int = DEFAULT_MAX_SEARCH_CANDIDATES
    sort_type_choice: int = 1
    search_note_time_choice: int = 0
    output_dir: str = "datas/batch_outputs"
    cache_path: str = "datas/cache/red_id_user_cache.jsonl"


@dataclass
class ResolvedUser:
    red_id: str
    user_id: str
    user_url: str
    nickname: str = ""
    source: str = "cache"
    raw_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    matched_keywords: List[str] = field(default_factory=list)
    matched_in_title: List[str] = field(default_factory=list)
    matched_in_desc: List[str] = field(default_factory=list)
    matched_in_tags: List[str] = field(default_factory=list)


@dataclass
class CollectedNote:
    note_id: str
    note_url: str
    cover_url: str
    title: str
    desc: str
    tags: List[str]
    author_nickname: str
    author_user_id: str
    red_id: str
    publish_time: Optional[datetime]
    liked_count: str
    collected_count: str
    comment_count: str
    share_count: str
    note_type: str = ""
    publish_time_text: str = ""
    detail_status: str = "detail"
    matched_keywords: List[str] = field(default_factory=list)
    matched_in_title: List[str] = field(default_factory=list)
    matched_in_desc: List[str] = field(default_factory=list)
    matched_in_tags: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    search_query: str = ""
    crawl_time: datetime = field(default_factory=datetime.now)
    raw_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlEvent:
    level: str
    event_type: str
    message: str
    channel: str = ""
    red_id: str = ""
    search_query: str = ""
    page: Optional[int] = None
    count: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
