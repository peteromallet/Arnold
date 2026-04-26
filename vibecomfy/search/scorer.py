from __future__ import annotations

from dataclasses import dataclass

from .aliases import alias_terms, expanded_terms, matched_aliases, normalize_text, tokenize
from .index import SearchEntry


@dataclass(frozen=True)
class SearchResult:
    entry: SearchEntry
    score: int
    reasons: tuple[str, ...] = ()


def score_entry(entry: SearchEntry, query: str, *, task: str | None = None) -> SearchResult:
    terms = expanded_terms(query, task)
    class_text = normalize_text(entry.class_type)
    pack_text = normalize_text(entry.pack or "")
    description_tokens = tokenize(entry.description)
    tag_tokens = set()
    for tag in entry.tags:
        tag_tokens.update(tokenize(tag))
        tag_tokens.add(normalize_text(tag))

    score = 0
    reasons: list[str] = []
    if class_text and (normalize_text(query) == class_text or class_text in terms):
        score += 5
        reasons.append("class_type")

    if _field_matches(pack_text, terms):
        score += 3
        reasons.append("pack")

    tag_hits = len(tag_tokens & terms)
    if tag_hits:
        score += 2 * tag_hits
        reasons.append("tag")

    description_hits = len(description_tokens & terms)
    if description_hits:
        score += description_hits
        reasons.append("description")

    alias_hits = _alias_hits(entry, query, task)
    if alias_hits:
        score += 2 * alias_hits
        reasons.append("alias")

    return SearchResult(entry=entry, score=score, reasons=tuple(reasons))


def search_entries(
    entries: list[SearchEntry],
    query: str,
    *,
    task: str | None = None,
    limit: int = 10,
) -> list[SearchResult]:
    results = [score_entry(entry, query, task=task) for entry in entries]
    ranked = [result for result in results if result.score > 0]
    ranked.sort(
        key=lambda result: (
            result.score,
            result.entry.source == "object_info",
            result.entry.source == "node_index",
            result.entry.class_type.lower(),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _field_matches(text: str, terms: set[str]) -> bool:
    if not text:
        return False
    tokens = tokenize(text)
    return text in terms or bool(tokens & terms)


def _alias_hits(entry: SearchEntry, query: str, task: str | None) -> int:
    haystack = " ".join(
        normalize_text(value)
        for value in [
            entry.class_type,
            entry.pack or "",
            entry.description,
            *entry.tags,
            *entry.tasks,
        ]
    )
    hits = 0
    for alias in matched_aliases(query, task):
        terms = alias_terms(alias)
        hits += sum(1 for term in terms if term and term in haystack)
    return hits
