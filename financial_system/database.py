from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from financial_system.config import DB_PATH
from financial_system.keywords import is_trackable_news_keyword
from financial_system.market import MarketSnapshot
from financial_system.monitor_bridge import MonitorEvent
from financial_system.news import NewsItem
from financial_system.risk_analyzer import RiskMetrics

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
    """
    CREATE TABLE IF NOT EXISTS tracked_keywords (
        term TEXT PRIMARY KEY,
        weight REAL NOT NULL,
        first_seen_day TEXT NOT NULL,
        last_seen_day TEXT NOT NULL,
        appearances INTEGER NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_reports (
        run_id TEXT PRIMARY KEY,
        day TEXT NOT NULL,
        report_markdown TEXT NOT NULL,
        ai_report TEXT,
        keyword_scores_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_metrics (
        day TEXT NOT NULL,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        region TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        metrics_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(day, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS monitor_events (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        event_type TEXT NOT NULL,
        symbol TEXT,
        title TEXT NOT NULL,
        severity TEXT NOT NULL,
        event_time TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
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
        _migrate_daily_reports_schema(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_reports_day_created_at ON daily_reports(day, created_at)"
        )
        connection.commit()


def _migrate_daily_reports_schema(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(daily_reports)").fetchall()
    if not columns:
        return
    column_names = {row["name"] for row in columns}
    primary_keys = {row["name"] for row in columns if int(row["pk"] or 0) > 0}
    if "run_id" in column_names and primary_keys == {"run_id"}:
        return

    connection.execute("ALTER TABLE daily_reports RENAME TO daily_reports_legacy")
    connection.execute(
        """
        CREATE TABLE daily_reports (
            run_id TEXT PRIMARY KEY,
            day TEXT NOT NULL,
            report_markdown TEXT NOT NULL,
            ai_report TEXT,
            keyword_scores_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO daily_reports
            (run_id, day, report_markdown, ai_report, keyword_scores_json, created_at)
        SELECT
            day || '_legacy',
            day,
            report_markdown,
            ai_report,
            keyword_scores_json,
            created_at
        FROM daily_reports_legacy
        """
    )
    connection.execute("DROP TABLE daily_reports_legacy")


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
        connection.execute("DELETE FROM keyword_trends WHERE day = ?", (day,))
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


def save_daily_report(
    day: str,
    run_id: str,
    report_markdown: str,
    ai_report: str | None,
    keyword_scores: dict[str, float],
) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_reports
                (run_id, day, report_markdown, ai_report, keyword_scores_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                day = excluded.day,
                report_markdown = excluded.report_markdown,
                ai_report = excluded.ai_report,
                keyword_scores_json = excluded.keyword_scores_json,
                created_at = excluded.created_at
            """,
            (
                run_id,
                day,
                report_markdown,
                ai_report,
                json.dumps(keyword_scores, ensure_ascii=False, sort_keys=True),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        connection.commit()


def load_daily_report(day: str) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT run_id, day, report_markdown, ai_report, keyword_scores_json, created_at
            FROM daily_reports
            WHERE day = ?
            ORDER BY created_at DESC, run_id DESC
            LIMIT 1
            """,
            (day,),
        ).fetchone()
    if row is None:
        return None
    try:
        keyword_scores = json.loads(row["keyword_scores_json"])
    except json.JSONDecodeError:
        keyword_scores = {}
    return {
        "run_id": row["run_id"],
        "day": row["day"],
        "report_markdown": row["report_markdown"],
        "ai_report": row["ai_report"],
        "keyword_scores": keyword_scores,
        "relevance": 0.0,
        "matched_terms": ["previous same-day run"],
        "created_at": row["created_at"],
        "context_role": "previous_same_day_run",
    }


def update_tracked_keyword_weights(
    day: str,
    keyword_scores: list[tuple[str, float]],
    decay: float = 0.85,
    min_weight: float = 0.25,
    max_weight: float = 25.0,
) -> None:
    """Decay older tracked keywords and boost terms that appeared in today's news."""
    now = datetime.now().isoformat(timespec="seconds")
    current_scores = {
        term.strip().lower(): float(score)
        for term, score in keyword_scores
        if term and float(score) > 0 and is_trackable_news_keyword(term)
    }
    with _connect() as connection:
        rows = connection.execute(
            "SELECT term, weight, first_seen_day, last_seen_day, appearances FROM tracked_keywords"
        ).fetchall()
        existing_terms = {row["term"] for row in rows}
        for row in rows:
            term = row["term"]
            if not is_trackable_news_keyword(term):
                connection.execute("DELETE FROM tracked_keywords WHERE term = ?", (term,))
                continue
            boost = current_scores.get(term, 0.0)
            same_day_update = row["last_seen_day"] == day
            if same_day_update:
                new_weight = max(float(row["weight"]), min(max_weight, boost)) if boost else float(row["weight"])
            else:
                decayed_weight = float(row["weight"]) * decay
                new_weight = min(max_weight, decayed_weight + boost)
            if new_weight < min_weight and not boost:
                connection.execute("DELETE FROM tracked_keywords WHERE term = ?", (term,))
                continue
            connection.execute(
                """
                UPDATE tracked_keywords
                SET weight = ?, last_seen_day = ?, appearances = ?, updated_at = ?
                WHERE term = ?
                """,
                (
                    new_weight,
                    day if boost else row["last_seen_day"],
                    int(row["appearances"]) + (1 if boost and not same_day_update else 0),
                    now,
                    term,
                ),
            )

        for term, score in current_scores.items():
            if term in existing_terms:
                continue
            connection.execute(
                """
                INSERT INTO tracked_keywords
                    (term, weight, first_seen_day, last_seen_day, appearances, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (term, min(max_weight, score), day, day, 1, now),
            )
        connection.commit()


def load_tracked_keyword_weights(
    limit: int = 20,
    min_weight: float = 1.0,
) -> dict[str, float]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT term, weight
            FROM tracked_keywords
            WHERE weight >= ?
            ORDER BY weight DESC, last_seen_day DESC, term
            LIMIT ?
            """,
            (min_weight, limit),
        ).fetchall()
    return {
        row["term"]: float(row["weight"])
        for row in rows
        if is_trackable_news_keyword(row["term"])
    }


def load_tracked_keywords(limit: int = 30) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT term, weight, first_seen_day, last_seen_day, appearances, updated_at
            FROM tracked_keywords
            ORDER BY weight DESC, last_seen_day DESC, term
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows if is_trackable_news_keyword(row["term"])]


def upsert_tracked_keywords(rows: list[dict]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    saved = 0
    with _connect() as connection:
        for row in rows:
            term = str(row.get("term", "")).strip().lower()
            if not is_trackable_news_keyword(term):
                continue
            try:
                weight = float(row.get("weight", 0) or 0)
            except (TypeError, ValueError):
                continue
            if weight <= 0:
                continue
            first_seen_day = str(row.get("first_seen_day") or row.get("last_seen_day") or "").strip()
            last_seen_day = str(row.get("last_seen_day") or first_seen_day).strip()
            if not first_seen_day or not last_seen_day:
                continue
            try:
                appearances = int(float(row.get("appearances", 1) or 1))
            except (TypeError, ValueError):
                appearances = 1
            updated_at = str(row.get("updated_at") or now)
            connection.execute(
                """
                INSERT INTO tracked_keywords
                    (term, weight, first_seen_day, last_seen_day, appearances, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(term) DO UPDATE SET
                    weight = excluded.weight,
                    first_seen_day = excluded.first_seen_day,
                    last_seen_day = excluded.last_seen_day,
                    appearances = excluded.appearances,
                    updated_at = excluded.updated_at
                """,
                (term, weight, first_seen_day, last_seen_day, appearances, updated_at),
            )
            saved += 1
        connection.commit()
    return saved


def save_risk_metrics(day: str, metrics: list[RiskMetrics]) -> None:
    rows = [
        (
            day,
            item.symbol,
            item.name,
            item.region,
            item.risk_level,
            json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True),
            datetime.now().isoformat(timespec="seconds"),
        )
        for item in metrics
    ]
    with _connect() as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO risk_metrics
                (day, symbol, name, region, risk_level, metrics_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()


def save_monitor_event(event: MonitorEvent) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO monitor_events
                (id, source, event_type, symbol, title, severity, event_time, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.source,
                event.event_type,
                event.symbol,
                event.title,
                event.severity,
                event.event_time,
                json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        connection.commit()


def save_monitor_events(events: list[MonitorEvent]) -> int:
    saved = 0
    for event in events:
        save_monitor_event(event)
        saved += 1
    return saved


def load_monitor_events(
    lookback_hours: int = 36,
    limit: int = 20,
) -> list[MonitorEvent]:
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    raw_limit = max(limit * 5, limit + 50)
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, source, event_type, symbol, title, severity, event_time, payload_json
            FROM monitor_events
            ORDER BY event_time DESC
            """
        ).fetchall()

    events: list[MonitorEvent] = []
    for row in rows:
        try:
            event_time = datetime.fromisoformat(row["event_time"].replace("Z", "+00:00"))
            if event_time.tzinfo is not None:
                event_time = event_time.replace(tzinfo=None)
        except ValueError:
            continue
        if event_time < cutoff:
            continue
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            payload = {}
        events.append(
            MonitorEvent(
                id=row["id"],
                source=row["source"],
                event_type=row["event_type"],
                symbol=row["symbol"],
                title=row["title"],
                severity=row["severity"],
                event_time=row["event_time"],
                payload=payload,
            )
        )
        if len(events) >= raw_limit:
            break
    return events


def load_related_reports(
    keyword_scores: dict[str, float],
    min_reports: int = 3,
    lookback_days: int = 45,
    exclude_days: set[str] | None = None,
) -> list[dict]:
    exclude_days = exclude_days or set()
    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT run_id, day, report_markdown, ai_report, keyword_scores_json, created_at
            FROM daily_reports
            ORDER BY day DESC
            """
        ).fetchall()

    candidates: list[dict] = []
    current_terms = {term: float(score) for term, score in keyword_scores.items() if score > 0}
    for row in rows:
        day = row["day"]
        if day in exclude_days:
            continue
        try:
            day_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day_date < cutoff:
            continue
        try:
            historical_terms = json.loads(row["keyword_scores_json"])
        except json.JSONDecodeError:
            historical_terms = {}

        relevance = 0.0
        matched_terms: list[str] = []
        for term, current_score in current_terms.items():
            historical_score = float(historical_terms.get(term, 0) or 0)
            if historical_score <= 0:
                continue
            relevance += current_score * historical_score
            matched_terms.append(term)

        candidates.append(
            {
                "run_id": row["run_id"],
                "day": day,
                "report_markdown": row["report_markdown"],
                "ai_report": row["ai_report"],
                "keyword_scores": historical_terms,
                "relevance": relevance,
                "matched_terms": matched_terms,
                "created_at": row["created_at"],
            }
        )

    ranked = sorted(
        candidates,
        key=lambda item: (item["relevance"], item["day"]),
        reverse=True,
    )
    selected = [item for item in ranked if item["relevance"] > 0][:min_reports]
    if len(selected) < min_reports:
        selected_days = {item["day"] for item in selected}
        for item in ranked:
            if item["day"] in selected_days:
                continue
            selected.append(item)
            selected_days.add(item["day"])
            if len(selected) >= min_reports:
                break
    return selected


def load_previous_report(day: str, lookback_days: int = 45) -> dict | None:
    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT run_id, day, report_markdown, ai_report, keyword_scores_json, created_at
            FROM daily_reports
            WHERE day < ?
            ORDER BY day DESC, created_at DESC, run_id DESC
            """,
            (day,),
        ).fetchall()

    for row in rows:
        try:
            day_date = datetime.strptime(row["day"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if day_date < cutoff:
            continue
        try:
            historical_terms = json.loads(row["keyword_scores_json"])
        except json.JSONDecodeError:
            historical_terms = {}
        return {
            "run_id": row["run_id"],
            "day": row["day"],
            "report_markdown": row["report_markdown"],
            "ai_report": row["ai_report"],
            "keyword_scores": historical_terms,
            "relevance": 0.0,
            "matched_terms": ["previous report"],
            "created_at": row["created_at"],
            "context_role": "previous_report",
        }
    return None


_sqlite_init_db = init_db
_sqlite_save_notes = save_notes
_sqlite_save_market_snapshots = save_market_snapshots
_sqlite_save_news = save_news
_sqlite_save_keyword_scores = save_keyword_scores
_sqlite_load_historical_keyword_scores = load_historical_keyword_scores
_sqlite_save_daily_report = save_daily_report
_sqlite_load_daily_report = load_daily_report
_sqlite_update_tracked_keyword_weights = update_tracked_keyword_weights
_sqlite_load_tracked_keyword_weights = load_tracked_keyword_weights
_sqlite_load_tracked_keywords = load_tracked_keywords
_sqlite_upsert_tracked_keywords = upsert_tracked_keywords
_sqlite_save_risk_metrics = save_risk_metrics
_sqlite_save_monitor_event = save_monitor_event
_sqlite_save_monitor_events = save_monitor_events
_sqlite_load_monitor_events = load_monitor_events
_sqlite_load_related_reports = load_related_reports
_sqlite_load_previous_report = load_previous_report


def _sheet_backend_config() -> tuple[bool, str | None]:
    import os

    from dotenv import load_dotenv

    from financial_system.config import ROOT

    load_dotenv(ROOT / ".env")
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID") or None
    enabled = os.getenv("GOOGLE_SHEET_STATE_BACKEND", "true").lower() == "true"
    return bool(enabled and spreadsheet_id), spreadsheet_id


def init_db() -> None:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import init_db as init_sheet_db

        init_sheet_db(spreadsheet_id)
        return
    _sqlite_init_db()


def save_notes(day: str, raw_notes: str) -> None:
    enabled, _ = _sheet_backend_config()
    if enabled:
        return
    _sqlite_save_notes(day, raw_notes)


def save_market_snapshots(day: str, snapshots: list[MarketSnapshot]) -> None:
    enabled, _ = _sheet_backend_config()
    if enabled:
        return
    _sqlite_save_market_snapshots(day, snapshots)


def save_news(day: str, news_items: list[NewsItem]) -> None:
    enabled, _ = _sheet_backend_config()
    if enabled:
        return
    _sqlite_save_news(day, news_items)


def save_keyword_scores(day: str, keyword_scores: list[tuple[str, float]]) -> None:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import save_keyword_scores as save_sheet_keyword_scores

        save_sheet_keyword_scores(spreadsheet_id, day, keyword_scores)
        return
    _sqlite_save_keyword_scores(day, keyword_scores)


def load_historical_keyword_scores(
    max_days: int = 14,
    decay: float = 0.85,
    min_score: float = 1.0,
    exclude_days: set[str] | None = None,
) -> dict[str, float]:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_historical_keyword_scores as load_sheet_scores

        return load_sheet_scores(spreadsheet_id, max_days, decay, min_score, exclude_days)
    return _sqlite_load_historical_keyword_scores(max_days, decay, min_score, exclude_days)


def save_daily_report(
    day: str,
    run_id: str,
    report_markdown: str,
    ai_report: str | None,
    keyword_scores: dict[str, float],
) -> None:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import save_daily_report as save_sheet_daily_report

        save_sheet_daily_report(spreadsheet_id, day, run_id, report_markdown, ai_report, keyword_scores)
        return
    _sqlite_save_daily_report(day, run_id, report_markdown, ai_report, keyword_scores)


def load_daily_report(day: str) -> dict | None:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_daily_report as load_sheet_daily_report

        return load_sheet_daily_report(spreadsheet_id, day)
    return _sqlite_load_daily_report(day)


def update_tracked_keyword_weights(
    day: str,
    keyword_scores: list[tuple[str, float]],
    decay: float = 0.85,
    min_weight: float = 0.25,
    max_weight: float = 25.0,
) -> None:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import update_tracked_keyword_weights as update_sheet_weights

        update_sheet_weights(spreadsheet_id, day, keyword_scores, decay, min_weight, max_weight)
        return
    _sqlite_update_tracked_keyword_weights(day, keyword_scores, decay, min_weight, max_weight)


def load_tracked_keyword_weights(limit: int = 20, min_weight: float = 1.0) -> dict[str, float]:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_tracked_keyword_weights as load_sheet_weights

        return load_sheet_weights(spreadsheet_id, limit, min_weight)
    return _sqlite_load_tracked_keyword_weights(limit, min_weight)


def load_tracked_keywords(limit: int = 30) -> list[dict]:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_tracked_keywords as load_sheet_keywords

        return load_sheet_keywords(spreadsheet_id, limit)
    return _sqlite_load_tracked_keywords(limit)


def upsert_tracked_keywords(rows: list[dict]) -> int:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import upsert_tracked_keywords as upsert_sheet_keywords

        return upsert_sheet_keywords(spreadsheet_id, rows)
    return _sqlite_upsert_tracked_keywords(rows)


def save_risk_metrics(day: str, metrics: list[RiskMetrics]) -> None:
    enabled, _ = _sheet_backend_config()
    if enabled:
        return
    _sqlite_save_risk_metrics(day, metrics)


def save_monitor_event(event: MonitorEvent) -> None:
    save_monitor_events([event])


def save_monitor_events(events: list[MonitorEvent]) -> int:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import save_monitor_events as save_sheet_monitor_events

        return save_sheet_monitor_events(spreadsheet_id, events)
    return _sqlite_save_monitor_events(events)


def load_monitor_events(lookback_hours: int = 36, limit: int = 20) -> list[MonitorEvent]:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_monitor_events as load_sheet_monitor_events

        return load_sheet_monitor_events(spreadsheet_id, lookback_hours, limit)
    return _sqlite_load_monitor_events(lookback_hours, limit)


def load_related_reports(
    keyword_scores: dict[str, float],
    min_reports: int = 3,
    lookback_days: int = 45,
    exclude_days: set[str] | None = None,
) -> list[dict]:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_related_reports as load_sheet_related_reports

        return load_sheet_related_reports(spreadsheet_id, keyword_scores, min_reports, lookback_days, exclude_days)
    return _sqlite_load_related_reports(keyword_scores, min_reports, lookback_days, exclude_days)


def load_previous_report(day: str, lookback_days: int = 45) -> dict | None:
    enabled, spreadsheet_id = _sheet_backend_config()
    if enabled and spreadsheet_id:
        from financial_system.google_sheet_database import load_previous_report as load_sheet_previous_report

        return load_sheet_previous_report(spreadsheet_id, day, lookback_days)
    return _sqlite_load_previous_report(day, lookback_days)
