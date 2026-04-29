from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from financial_system.config import load_keyword_weights, load_policy_keywords


STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "for",
    "from",
    "has",
    "have",
    "into",
    "less",
    "more",
    "not",
    "that",
    "the",
    "their",
    "this",
    "today",
    "was",
    "were",
    "with",
    "will",
}


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9&.-]{2,}")

WEIGHTED_NOTE_PATTERN = re.compile(
    r"(?P<term>[A-Za-z][A-Za-z0-9&. \-]{2,}?)\s*\[\s*(?:weight|w)\s*[:=]\s*(?P<weight>\d+)\s*\]",
    re.IGNORECASE,
)


def _clean_token(token: str) -> str:
    token = token.strip().lower()
    return token


def _extract_terms(text: str) -> Iterable[str]:
    for match in TOKEN_PATTERN.findall(text.lower()):
        if match not in STOPWORDS:
            yield match


def _extract_weighted_notes(text: str) -> dict[str, int]:
    weights: dict[str, int] = {}
    for match in WEIGHTED_NOTE_PATTERN.finditer(text):
        term = _clean_token(match.group("term"))
        weight = int(match.group("weight"))
        if term and weight > 0:
            weights[term] = max(weights.get(term, 0), weight)
    return weights


def _phrase_candidates(text: str) -> Iterable[str]:
    words = [word for word in TOKEN_PATTERN.findall(text.lower()) if word not in STOPWORDS]
    for i in range(len(words) - 1):
        yield f"{words[i]} {words[i + 1]}"


def rank_keywords(text: str, limit: int = 12) -> list[tuple[str, int]]:
    if not text:
        return []

    config_weights = load_keyword_weights()
    manual_weights = _extract_weighted_notes(text)
    searchable_text = WEIGHTED_NOTE_PATTERN.sub(lambda match: match.group("term"), text)
    counter = Counter(_extract_terms(searchable_text))
    counter.update(_phrase_candidates(searchable_text))

    scores: Counter[str] = Counter()
    for term, count in counter.items():
        score = count
        score += config_weights.get(term, 0)
        score += manual_weights.get(term, 0)
        if score > 0:
            scores[term] = score

    return scores.most_common(limit)


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    return [term for term, _ in rank_keywords(text, limit=limit)]


def blend_keywords(
    current_scores: list[tuple[str, float]],
    historical_scores: dict[str, float],
    primary_limit: int = 12,
    secondary_limit: int = 4,
) -> tuple[list[str], list[str]]:
    current_terms = [term for term, _ in current_scores[:primary_limit]]
    remaining = {
        term: score
        for term, score in historical_scores.items()
        if term not in current_terms
    }
    secondary_terms = [term for term, _ in sorted(remaining.items(), key=lambda item: item[1], reverse=True)][:secondary_limit]
    return current_terms, secondary_terms


def build_keyword_queries(keywords: list[str], max_queries: int = 8) -> list[str]:
    return [f"{keyword} financial market news" for keyword in keywords[:max_queries]]


def build_policy_queries(
    snapshots: list[object],
    policy_limit: int = 8,
    company_limit: int = 8,
) -> list[str]:
    config = load_policy_keywords()
    terms = config.get("terms", [])[:policy_limit]
    company_terms = config.get("company_terms", {})
    tracked_symbols = {getattr(snapshot, "symbol", "") for snapshot in snapshots}

    queries = [f"{term} stock market impact" for term in terms]
    added_company_terms = 0
    for symbol, terms_for_symbol in company_terms.items():
        if symbol not in tracked_symbols:
            continue
        for term in terms_for_symbol:
            if added_company_terms >= company_limit:
                break
            queries.append(f"{term} stock impact")
            added_company_terms += 1
        if added_company_terms >= company_limit:
            break
    return queries


def build_trend_queries(
    trend_config: dict[str, list[str]],
    max_queries: int = 8,
) -> list[str]:
    queries: list[str] = []
    for category, terms in trend_config.items():
        for term in terms[: max(1, max_queries // len(trend_config))]:
            if len(queries) >= max_queries:
                break
            queries.append(f"{term} industry trend news")
            queries.append(f"{category} investment rotation news")
        if len(queries) >= max_queries:
            break
    return queries[:max_queries]
