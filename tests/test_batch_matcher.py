from spider.batch_matcher import match_note_keywords, normalize_for_match


def test_normalize_for_match_removes_spaces_case_and_punctuation():
    assert normalize_for_match("AI 客服，增长!") == "ai客服增长"


def test_match_note_keywords_records_fields():
    result = match_note_keywords(
        title="艾 薇 岚 大超炮体验",
        desc="北京门店项目记录",
        tags=["医美", "大 超 炮"],
        keywords=["艾薇岚", "大超炮", "北京", "上海"],
    )

    assert result.matched_keywords == ["艾薇岚", "大超炮", "北京"]
    assert result.matched_in_title == ["艾薇岚", "大超炮"]
    assert result.matched_in_desc == ["北京"]
    assert result.matched_in_tags == ["大超炮"]


def test_match_note_keywords_returns_empty_when_no_hit():
    result = match_note_keywords(
        title="日常护肤记录",
        desc="今天分享补水",
        tags=["护肤"],
        keywords=["艾薇岚"],
    )

    assert result.matched_keywords == []
    assert result.matched_in_title == []
    assert result.matched_in_desc == []
    assert result.matched_in_tags == []
