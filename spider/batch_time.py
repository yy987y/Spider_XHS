from __future__ import annotations

from datetime import datetime, time, timedelta

from spider.batch_models import DateRange


def _day_start(value):
    return datetime.combine(value.date(), time(0, 0, 0))


def _day_end(value):
    return datetime.combine(value.date(), time(23, 59, 59))


def parse_date_range(value: str, now: datetime | None = None) -> DateRange:
    now = now or datetime.now()
    normalized = (value or "").strip()
    if normalized in ("", "recent_7_days", "近7天"):
        start_day = now - timedelta(days=6)
        return DateRange(start=_day_start(start_day), end=_day_end(now), label="近7天")
    if normalized in ("recent_30_days", "近30天"):
        start_day = now - timedelta(days=29)
        return DateRange(start=_day_start(start_day), end=_day_end(now), label="近30天")
    if ":" in normalized:
        start_text, end_text = normalized.split(":", 1)
        start = datetime.strptime(start_text.strip(), "%Y-%m-%d")
        end = datetime.strptime(end_text.strip(), "%Y-%m-%d")
        if start > end:
            raise ValueError(f"开始日期不能晚于结束日期: {normalized}")
        return DateRange(
            start=_day_start(start),
            end=_day_end(end),
            label=f"{start_text.strip()}_{end_text.strip()}",
        )
    raise ValueError(f"不支持的时间范围: {value}")


def is_in_range(publish_time: datetime, date_range: DateRange) -> bool:
    return date_range.start <= publish_time <= date_range.end


def is_before_range(publish_time: datetime, date_range: DateRange) -> bool:
    return publish_time < date_range.start
