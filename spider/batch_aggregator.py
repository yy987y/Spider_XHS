from __future__ import annotations

from spider.batch_models import CollectedNote


def _merge_unique(existing: list, new_values: list) -> list:
    result = list(existing or [])
    for value in new_values or []:
        if value not in result:
            result.append(value)
    return result


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
        if note.search_query and note.search_query not in existing.search_query:
            existing.search_query = ", ".join([v for v in [existing.search_query, note.search_query] if v])

    def items(self) -> list[CollectedNote]:
        return list(self._notes.values())

    def __len__(self) -> int:
        return len(self._notes)
