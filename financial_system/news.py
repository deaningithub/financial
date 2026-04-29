from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
import json
import re
from urllib.parse import quote_plus

import feedparser

from financial_system.config import load_news_sources


@dataclass
class NewsItem:
    query: str
    title: str
    source: str
    link: str
    published: str | None


STOP_TOKENS = {
    "and",
    "are",
    "for",
    "from",
    "impact",
    "market",
    "news",
    "reason",
    "stock",
    "the",
    "today",
    "trend",
    "why",
}


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9.-]{2,}", value)
        if token.lower() not in STOP_TOKENS
    }


def _published_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _locale_settings(locale: str) -> tuple[str, str, str]:
    locale = locale.upper()
    if locale == "TW":
        return "zh-TW", "TW", "TW:zh-Hant"
    return "en-US", locale, f"{locale}:en"


def search_google_news(
    query: str,
    limit: int = 5,
    max_age_days: int = 14,
    locale: str = "US",
) -> list[NewsItem]:
    dated_query = f"{query} when:{max_age_days}d"
    hl, gl, ceid = _locale_settings(locale)
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(dated_query)}&hl={hl}&gl={gl}&ceid={ceid}"
    )
    feed = feedparser.parse(url)
    items: list[NewsItem] = []
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    for entry in feed.entries:
        published = getattr(entry, "published", None)
        published_at = _published_datetime(published)
        if published_at and published_at < cutoff:
            continue
        source = getattr(getattr(entry, "source", None), "title", "Google News")
        items.append(
            NewsItem(
                query=query,
                title=getattr(entry, "title", ""),
                source=source,
                link=getattr(entry, "link", ""),
                published=published,
            )
        )
        if len(items) >= limit:
            break
    return items


def search_source_feed(
    query: str,
    source: dict,
    limit: int = 3,
    max_age_days: int = 14,
) -> list[NewsItem]:
    if not source.get("enabled", True):
        return []
    feed = feedparser.parse(source["url"])
    query_tokens = _tokens(query)
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    items: list[NewsItem] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")
        published = getattr(entry, "published", None)
        published_at = _published_datetime(published)
        if published_at and published_at < cutoff:
            continue
        if query_tokens and not (query_tokens & _tokens(f"{title} {summary}")):
            continue
        items.append(
            NewsItem(
                query=query,
                title=title,
                source=source.get("name", "RSS"),
                link=getattr(entry, "link", ""),
                published=published,
            )
        )
        if len(items) >= limit:
            break
    return items


def collect_news(
    queries: list[str],
    limit_per_query: int = 5,
    max_age_days: int = 14,
    locales: list[str] | None = None,
    source_limit: int = 20,
) -> list[NewsItem]:
    if locales is None:
        locales = ["US"]
    seen: set[str] = set()
    results: list[NewsItem] = []
    for locale in locales:
        for query in queries:
            for item in search_google_news(
                query,
                limit=limit_per_query,
                max_age_days=max_age_days,
                locale=locale,
            ):
                key = item.link or item.title
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
    sources = load_news_sources()
    source_count = 0
    for query in queries:
        for source in sources:
            if source_count >= source_limit:
                return results
            for item in search_source_feed(
                query,
                source,
                limit=2,
                max_age_days=max_age_days,
            ):
                key = item.link or item.title
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
                source_count += 1
                if source_count >= source_limit:
                    return results
    return results


def save_news(path: Path, news_items: list[NewsItem]) -> None:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "items": [asdict(item) for item in news_items],
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")
