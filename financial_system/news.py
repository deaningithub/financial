from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
import json
from urllib.parse import quote_plus

import feedparser


@dataclass
class NewsItem:
    query: str
    title: str
    source: str
    link: str
    published: str | None


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


def collect_news(
    queries: list[str],
    limit_per_query: int = 5,
    max_age_days: int = 14,
    locales: list[str] | None = None,
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
    return results


def save_news(path: Path, news_items: list[NewsItem]) -> None:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "items": [asdict(item) for item in news_items],
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")
