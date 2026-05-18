import re
import string
from typing import Iterable, List

from spider.batch_models import MatchResult

_CN_PUNCTUATION = "，。！？、；：「」『』（）【】《》“”‘’—…·￥"
_PUNCT_TRANSLATION = str.maketrans("", "", string.punctuation + _CN_PUNCTUATION)


def normalize_for_match(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.casefold()
    text = re.sub(r"\s+", "", text)
    return text.translate(_PUNCT_TRANSLATION)


def _field_hits(field_text: object, keywords: Iterable[str]) -> List[str]:
    normalized_field = normalize_for_match(field_text)
    hits = []
    for keyword in keywords:
        normalized_keyword = normalize_for_match(keyword)
        if normalized_keyword and normalized_keyword in normalized_field:
            hits.append(keyword)
    return hits


def match_note_keywords(
    title: str, desc: str, tags: List[str], keywords: List[str]
) -> MatchResult:
    matched_in_title = _field_hits(title, keywords)
    matched_in_desc = _field_hits(desc, keywords)
    tag_text = " ".join(tags or [])
    matched_in_tags = _field_hits(tag_text, keywords)
    matched_keywords = []
    for keyword in keywords:
        if (
            keyword in matched_in_title
            or keyword in matched_in_desc
            or keyword in matched_in_tags
        ):
            matched_keywords.append(keyword)
    return MatchResult(
        matched_keywords=matched_keywords,
        matched_in_title=matched_in_title,
        matched_in_desc=matched_in_desc,
        matched_in_tags=matched_in_tags,
    )
