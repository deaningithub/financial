from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from financial_system.config import DB_PATH
from financial_system.market import MarketSnapshot
from financial_system.news import NewsItem

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS notes (
        day TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        note TEXT NOT NULL,
        PRIMARY KEY(day, timestamp, note)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_snapshots (
        day TEXT NOT NULL,
        symbol TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        PRIMARY KEY(day, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_items (
        day TEXT NOT NULL,
        query TEXT NOT NULL,
        title TEXT NOT NULL,
        source TEXT NOT NULL,
        link TEXT NOT NULL,
        published TEXT,
        PRIMARY KEY(day, link)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS keyword_trends (
        day TEXT NOT NULL,
        term TEXT NOT NULL,
        score REAL NOT NULL,
        PRIMARY KEY(day, term)
    )
    """,
]


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        for sql in CREATE_TABLES_SQL:
            connection.execute(sql)
        connection.commit()


def save_notes(day: str, raw_notes: str) -> None:
    lines = []
    for raw_line in raw_notes.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- [") and "]" in line:
            content = line.split("]", 1)[1].strip()
        else:
            content = line
        if content:
            timestamp = line[3:line.index("]")] if line.startswith("- [") and "]" in line else ""
            lines.append((day, timestamp, content))

    with _connect() as connection:
        connection.execute("DELETE FROM notes WHERE day = ?", (day,))
        connection.executemany(
            "INSERT OR IGNORE INTO notes (day, timestamp, note) VALUES (?, ?, ?)",
            lines,
        )
        connection.commit()


def save_market_snapshots(day: str, snapshots: list[MarketSnapshot]) -> None:
    rows: list[tuple[str, str, str]] = []
    for snapshot in snapshots:
        rows.append((day, snapshot.symbol, json.dumps(snapshot.__dict__, default=str)))
    with _connect() as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO market_snapshots (day, symbol, snapshot_json) VALUES (?, ?, ?)",
            rows,
        )
        connection.commit()


def save_news(day: str, news_items: list[NewsItem]) -> None:
    rows = [
        (
            day,
            item.query,
            item.title,
            item.source,
            item.link,
            item.published,
        )
        for item in news_items
    ]
    with _connect() as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO news_items (day, query, title, source, link, published) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()


def save_keyword_scores(day: str, keyword_scores: list[tuple[str, float]]) -> None:
    rows = [(day, term, float(score)) for term, score in keyword_scores]
    with _connect() as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO keyword_trends (day, term, score) VALUES (?, ?, ?)",
            rows,
        )
        connection.commit()


def load_historical_keyword_scores(
    max_days: int = 14,
    decay: float = 0.85,
    min_score: float = 1.0,
    exclude_days: set[str] | None = None,
) -> dict[str, float]:
    exclude_days = exclude_days or set()
    cutoff = datetime.utcnow().date() - timedelta(days=max_days)
    aggregated: dict[str, float] = {}
    with _connect() as connection:
        rows = connection.execute(
            "SELECT day, term, score FROM keyword_trends ORDER BY day DESC"
        ).fetchall()
    for row in rows:
        try:
            day_date = datetime.strptime(row["day"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if row["day"] in exclude_days:
            continue
        if day_date < cutoff:
            continue
        age = (datetime.utcnow().date() - day_date).days
        weighted_score = float(row["score"]) * (decay ** age)
        if weighted_score < min_score:
            continue
        aggregated[row["term"]] = aggregated.get(row["term"], 0.0) + weighted_score
    return aggregated
