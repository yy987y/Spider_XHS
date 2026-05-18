from __future__ import annotations

from spider.batch_models import CollectedNote


def _merge_unique(existing: list, new_values: list) -> list:
    result = list(existing or [])
    for value in new_values or []:
        if value not in result:
            result.append(value)
    return result


def _merge_search_query(existing: str, new_query: str) -> str:
    queries = [query for query in (existing or "").split(", ") if query]
    if new_query and new_query not in queries:
        queries.append(new_query)
    return ", ".join(queries)


class NoteAggregator:
    def __init__(self):
        self._notes = {}

    def add(self, note: CollectedNote) -> None:
        if note.note_id not in self._notes:
            self._notes[note.note_id] = note
            return
        existing = self._notes[note.note_id]
        existing.sources = _merge_unique(existing.sources, note.sources)
        existing.matched_keywords = _merge_unique(existing.matched_keywords, note.matched_keywords)
        existing.matched_in_title = _merge_unique(existing.matched_in_title, note.matched_in_title)
        existing.matched_in_desc = _merge_unique(existing.matched_in_desc, note.matched_in_desc)
        existing.matched_in_tags = _merge_unique(existing.matched_in_tags, note.matched_in_tags)
        existing.search_query = _merge_search_query(existing.search_query, note.search_query)

    def items(self) -> list[CollectedNote]:
        return list(self._notes.values())

    def __len__(self) -> int:
        return len(self._notes)
