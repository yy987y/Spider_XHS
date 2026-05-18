from datetime import datetime

from spider.batch_aggregator import NoteAggregator
from spider.batch_models import CollectedNote


def make_note(note_id, source, keywords, search_query="艾薇岚 大超炮 北京"):
    return CollectedNote(
        note_id=note_id,
        note_url=f"https://www.xiaohongshu.com/explore/{note_id}",
        cover_url="https://cover",
        title="标题",
        desc="描述",
        tags=["标签"],
        author_nickname="作者",
        author_user_id="u1",
        red_id="r1",
        publish_time=datetime(2026, 5, 18, 12, 0, 0),
        liked_count="1",
        collected_count="2",
        comment_count="3",
        share_count="4",
        matched_keywords=keywords,
        matched_in_title=keywords,
        matched_in_desc=keywords,
        matched_in_tags=keywords,
        sources=[source],
        search_query=search_query,
    )


def test_aggregator_merges_duplicate_note_sources_and_keywords():
    aggregator = NoteAggregator()

    aggregator.add(make_note("n1", "user", ["艾薇岚"]))
    aggregator.add(make_note("n1", "search", ["北京"]))

    notes = aggregator.items()

    assert len(notes) == 1
    assert notes[0].sources == ["user", "search"]
    assert notes[0].matched_keywords == ["艾薇岚", "北京"]
    assert notes[0].matched_in_title == ["艾薇岚", "北京"]
    assert notes[0].matched_in_desc == ["艾薇岚", "北京"]
    assert notes[0].matched_in_tags == ["艾薇岚", "北京"]


def test_aggregator_merges_search_queries_by_exact_value():
    aggregator = NoteAggregator()

    aggregator.add(make_note("n1", "user", ["艾薇岚"], search_query="艾薇岚 大超炮 北京"))
    aggregator.add(make_note("n1", "search", ["大超炮"], search_query="大超炮"))

    notes = aggregator.items()

    assert notes[0].search_query == "艾薇岚 大超炮 北京, 大超炮"


def test_aggregator_len_returns_deduplicated_note_count():
    aggregator = NoteAggregator()

    aggregator.add(make_note("n1", "user", ["艾薇岚"]))
    aggregator.add(make_note("n1", "search", ["北京"]))
    aggregator.add(make_note("n2", "search", ["大超炮"]))

    assert len(aggregator) == 2
