from datetime import datetime

from spider.batch_time import parse_date_range


def test_parse_recent_7_days_includes_calendar_boundaries():
    now = datetime(2026, 5, 18, 16, 30, 0)

    result = parse_date_range("recent_7_days", now=now)

    assert result.start == datetime(2026, 5, 12, 0, 0, 0)
    assert result.end == datetime(2026, 5, 18, 23, 59, 59)
    assert result.label == "近7天"


def test_parse_custom_date_range_includes_start_and_end_days():
    now = datetime(2026, 5, 18, 16, 30, 0)

    result = parse_date_range("2026-05-01:2026-05-18", now=now)

    assert result.start == datetime(2026, 5, 1, 0, 0, 0)
    assert result.end == datetime(2026, 5, 18, 23, 59, 59)
    assert result.label == "2026-05-01_2026-05-18"
