from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Iterable

from googleapiclient.discovery import build

from financial_system.google_auth import SHEETS_SCOPES, ensure_google_credentials
from financial_system.google_sheet_exporter import SHEETS as EXPORT_SHEETS
from financial_system.keywords import is_trackable_news_keyword
from financial_system.monitor_bridge import MonitorEvent


SHEETS = {
    **EXPORT_SHEETS,
    "MonitorEvents": [
        "id",
        "source",
        "event_type",
        "symbol",
        "title",
        "severity",
        "event_time",
        "payload_json",
        "created_at",
    ],
}

_SESSION_MONITOR_EVENTS: dict[str, MonitorEvent] = {}
MAX_CELL_CHARS = 45000


def _clip(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    text = str(value)
    if len(text) > MAX_CELL_CHARS:
        return text[:MAX_CELL_CHARS] + "\n[truncated]"
    return text


def _service():
    credentials, _ = ensure_google_credentials(SHEETS_SCOPES)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _values(service, spreadsheet_id: str, title: str) -> list[list[object]]:
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{title}!A:Z")
        .execute()
    )
    return response.get("values", [])


def _write_values(service, spreadsheet_id: str, title: str, rows: list[list[object]]) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"{title}!A:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()


def _ensure_sheets(service, spreadsheet_id: str) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_titles = {sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])}
    requests = [
        {"addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": 1000, "columnCount": 26}}}}
        for title in SHEETS
        if title not in existing_titles
    ]
    if requests:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()

    for title, headers in SHEETS.items():
        rows = _values(service, spreadsheet_id, title)
        if not rows or rows[0][: len(headers)] != headers:
            body_rows = rows[1:]
            if title == "DailyReports" and rows and rows[0] and rows[0][0] == "day":
                body_rows = [
                    [f"{row[0]}_legacy_sheet_{index}", *row]
                    for index, row in enumerate(body_rows, start=1)
                    if row
                ]
            _write_values(service, spreadsheet_id, title, [headers] + body_rows)


def init_db(spreadsheet_id: str) -> None:
    service = _service()
    _ensure_sheets(service, spreadsheet_id)


def _dict_rows(spreadsheet_id: str, title: str) -> list[dict]:
    service = _service()
    _ensure_sheets(service, spreadsheet_id)
    rows = _values(service, spreadsheet_id, title)
    if len(rows) < 2:
        return []
    headers = [str(header) for header in rows[0]]
    return [
        {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        for row in rows[1:]
        if row
    ]


def _replace_all_dicts(spreadsheet_id: str, title: str, rows: Iterable[dict]) -> None:
    service = _service()
    _ensure_sheets(service, spreadsheet_id)
    headers = SHEETS[title]
    _write_values(
        service,
        spreadsheet_id,
        title,
        [headers] + [[_clip(row.get(header, "")) for header in headers] for row in rows],
    )


def _replace_by_day(spreadsheet_id: str, title: str, day: str, rows: Iterable[dict]) -> None:
    existing = _dict_rows(spreadsheet_id, title)
    kept = [row for row in existing if row.get("day") != day]
    _replace_all_dicts(spreadsheet_id, title, kept + list(rows))


def _replace_by_key(spreadsheet_id: str, title: str, key: str, value: str, rows: Iterable[dict]) -> None:
    existing = _dict_rows(spreadsheet_id, title)
    kept = [row for row in existing if row.get(key) != value]
    _replace_all_dicts(spreadsheet_id, title, kept + list(rows))


def save_keyword_scores(spreadsheet_id: str, day: str, keyword_scores: list[tuple[str, float]]) -> None:
    updated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    _replace_by_day(
        spreadsheet_id,
        "KeywordTrends",
        day,
        [{"day": day, "term": term, "score": float(score), "updated_at": updated_at} for term, score in keyword_scores],
    )


def load_historical_keyword_scores(
    spreadsheet_id: str,
    max_days: int = 14,
    decay: float = 0.85,
    min_score: float = 1.0,
    exclude_days: set[str] | None = None,
) -> dict[str, float]:
    exclude_days = exclude_days or set()
    cutoff = datetime.utcnow().date() - timedelta(days=max_days)
    aggregated: dict[str, float] = {}
    for row in _dict_rows(spreadsheet_id, "KeywordTrends"):
        day = str(row.get("day", ""))
        try:
            day_date = datetime.strptime(day, "%Y-%m-%d").date()
            score = float(row.get("score", 0) or 0)
        except ValueError:
            continue
        if day in exclude_days or day_date < cutoff:
            continue
        weighted_score = score * (decay ** (datetime.utcnow().date() - day_date).days)
        if weighted_score >= min_score:
            term = str(row.get("term", ""))
            aggregated[term] = aggregated.get(term, 0.0) + weighted_score
    return aggregated


def load_tracked_keywords(spreadsheet_id: str, limit: int = 30) -> list[dict]:
    rows = [row for row in _dict_rows(spreadsheet_id, "KeywordWeights") if is_trackable_news_keyword(str(row.get("term", "")))]
    for row in rows:
        try:
            row["weight"] = float(row.get("weight", 0) or 0)
            row["appearances"] = int(float(row.get("appearances", 1) or 1))
        except ValueError:
            row["weight"] = 0.0
            row["appearances"] = 1
    rows.sort(key=lambda item: (float(item.get("weight", 0) or 0), str(item.get("last_seen_day", ""))), reverse=True)
    return rows[:limit]


def load_tracked_keyword_weights(spreadsheet_id: str, limit: int = 20, min_weight: float = 1.0) -> dict[str, float]:
    return {
        str(row.get("term", "")).strip().lower(): float(row.get("weight", 0) or 0)
        for row in load_tracked_keywords(spreadsheet_id, limit=limit)
        if float(row.get("weight", 0) or 0) >= min_weight
    }


def upsert_tracked_keywords(spreadsheet_id: str, rows: list[dict]) -> int:
    existing = {str(row.get("term", "")).strip().lower(): row for row in _dict_rows(spreadsheet_id, "KeywordWeights")}
    now = datetime.now().isoformat(timespec="seconds")
    saved = 0
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
        existing[term] = {
            "term": term,
            "weight": weight,
            "first_seen_day": row.get("first_seen_day") or row.get("last_seen_day") or now[:10],
            "last_seen_day": row.get("last_seen_day") or row.get("first_seen_day") or now[:10],
            "appearances": int(float(row.get("appearances", 1) or 1)),
            "updated_at": row.get("updated_at") or now,
        }
        saved += 1
    _replace_all_dicts(spreadsheet_id, "KeywordWeights", existing.values())
    return saved


def update_tracked_keyword_weights(
    spreadsheet_id: str,
    day: str,
    keyword_scores: list[tuple[str, float]],
    decay: float = 0.85,
    min_weight: float = 0.25,
    max_weight: float = 25.0,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    current_scores = {
        term.strip().lower(): float(score)
        for term, score in keyword_scores
        if term and float(score) > 0 and is_trackable_news_keyword(term)
    }
    existing = {str(row.get("term", "")).strip().lower(): row for row in _dict_rows(spreadsheet_id, "KeywordWeights")}
    for term, row in list(existing.items()):
        if not is_trackable_news_keyword(term):
            existing.pop(term, None)
            continue
        old_weight = float(row.get("weight", 0) or 0)
        boost = current_scores.get(term, 0.0)
        same_day_update = row.get("last_seen_day") == day
        if same_day_update:
            new_weight = max(old_weight, min(max_weight, boost)) if boost else old_weight
        else:
            new_weight = min(max_weight, old_weight * decay + boost)
        if new_weight < min_weight and not boost:
            existing.pop(term, None)
            continue
        row["weight"] = new_weight
        row["last_seen_day"] = day if boost else row.get("last_seen_day", "")
        row["appearances"] = int(float(row.get("appearances", 1) or 1)) + (1 if boost and not same_day_update else 0)
        row["updated_at"] = now

    for term, score in current_scores.items():
        if term not in existing:
            existing[term] = {
                "term": term,
                "weight": min(max_weight, score),
                "first_seen_day": day,
                "last_seen_day": day,
                "appearances": 1,
                "updated_at": now,
            }
    _replace_all_dicts(spreadsheet_id, "KeywordWeights", existing.values())


def save_daily_report(
    spreadsheet_id: str,
    day: str,
    run_id: str,
    report_markdown: str,
    ai_report: str | None,
    keyword_scores: dict[str, float],
) -> None:
    _replace_by_key(
        spreadsheet_id,
        "DailyReports",
        "run_id",
        run_id,
        [
            {
                "run_id": run_id,
                "day": day,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "ai_report": ai_report or "",
                "report_markdown": report_markdown,
            }
        ],
    )


def _report_from_row(row: dict, context_role: str | None = None) -> dict:
    result = {
        "run_id": row.get("run_id", ""),
        "day": row.get("day", ""),
        "report_markdown": row.get("report_markdown", ""),
        "ai_report": row.get("ai_report", ""),
        "keyword_scores": {},
        "relevance": 0.0,
        "matched_terms": [],
        "created_at": row.get("created_at", ""),
    }
    if context_role:
        result["context_role"] = context_role
    return result


def load_daily_report(spreadsheet_id: str, day: str) -> dict | None:
    rows = [row for row in _dict_rows(spreadsheet_id, "DailyReports") if row.get("day") == day]
    if not rows:
        return None
    rows.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("run_id", ""))), reverse=True)
    report = _report_from_row(rows[0], "previous_same_day_run")
    report["matched_terms"] = ["previous same-day run"]
    return report


def load_previous_report(spreadsheet_id: str, day: str, lookback_days: int = 45) -> dict | None:
    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    rows = []
    for row in _dict_rows(spreadsheet_id, "DailyReports"):
        row_day = str(row.get("day", ""))
        try:
            day_date = datetime.strptime(row_day, "%Y-%m-%d").date()
        except ValueError:
            continue
        if cutoff <= day_date and row_day < day:
            rows.append(row)
    if not rows:
        return None
    rows.sort(key=lambda item: (str(item.get("day", "")), str(item.get("created_at", ""))), reverse=True)
    report = _report_from_row(rows[0], "previous_report")
    report["matched_terms"] = ["previous report"]
    return report


def load_related_reports(
    spreadsheet_id: str,
    keyword_scores: dict[str, float],
    min_reports: int = 3,
    lookback_days: int = 45,
    exclude_days: set[str] | None = None,
) -> list[dict]:
    exclude_days = exclude_days or set()
    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    rows = []
    for row in _dict_rows(spreadsheet_id, "DailyReports"):
        day = str(row.get("day", ""))
        try:
            day_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day not in exclude_days and day_date >= cutoff:
            rows.append(_report_from_row(row))
    rows.sort(key=lambda item: (str(item.get("day", "")), str(item.get("created_at", ""))), reverse=True)
    return rows[:min_reports]


def save_monitor_events(spreadsheet_id: str, events: list[MonitorEvent]) -> int:
    existing = {str(row.get("id", "")): row for row in _dict_rows(spreadsheet_id, "MonitorEvents")}
    now = datetime.now().isoformat(timespec="seconds")
    for event in events:
        _SESSION_MONITOR_EVENTS[event.id] = event
        existing[event.id] = {
            "id": event.id,
            "source": event.source,
            "event_type": event.event_type,
            "symbol": event.symbol or "",
            "title": event.title,
            "severity": event.severity,
            "event_time": event.event_time,
            "payload_json": json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
            "created_at": now,
        }
    _replace_all_dicts(spreadsheet_id, "MonitorEvents", existing.values())
    return len(events)


def load_monitor_events(spreadsheet_id: str, lookback_hours: int = 36, limit: int = 20) -> list[MonitorEvent]:
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    events: dict[str, MonitorEvent] = dict(_SESSION_MONITOR_EVENTS)
    for row in _dict_rows(spreadsheet_id, "MonitorEvents"):
        event_id = str(row.get("id", ""))
        if not event_id:
            continue
        try:
            payload = json.loads(str(row.get("payload_json", "{}") or "{}"))
        except json.JSONDecodeError:
            payload = {}
        events[event_id] = MonitorEvent(
            id=event_id,
            source=str(row.get("source", "")),
            event_type=str(row.get("event_type", "")),
            symbol=str(row.get("symbol", "")) or None,
            title=str(row.get("title", "")),
            severity=str(row.get("severity", "medium")),
            event_time=str(row.get("event_time", "")),
            payload=payload,
        )

    filtered: list[MonitorEvent] = []
    for event in events.values():
        try:
            event_time = datetime.fromisoformat(event.event_time.replace("Z", "+00:00"))
            if event_time.tzinfo is not None:
                event_time = event_time.replace(tzinfo=None)
        except ValueError:
            continue
        if event_time >= cutoff:
            filtered.append(event)
    filtered.sort(key=lambda item: item.event_time, reverse=True)
    return filtered[:limit]
