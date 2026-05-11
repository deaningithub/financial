from __future__ import annotations

from datetime import datetime
from typing import Iterable

import google.auth
from googleapiclient.discovery import build

from financial_system.market import MarketSnapshot
from financial_system.news import NewsItem
from financial_system.risk_analyzer import RiskMetrics


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
MAX_CELL_CHARS = 45000


SHEETS: dict[str, list[str]] = {
    "DailyReports": [
        "day",
        "created_at",
        "report_path",
        "news_count",
        "market_snapshot_count",
        "risk_metric_count",
        "sheet_monitor_sync",
        "sheet_keyword_seed",
        "ai_report",
        "report_markdown",
    ],
    "KeywordWeights": [
        "term",
        "weight",
        "first_seen_day",
        "last_seen_day",
        "appearances",
        "updated_at",
    ],
    "KeywordTrends": ["day", "term", "score", "updated_at"],
    "MarketSnapshots": [
        "day",
        "symbol",
        "name",
        "asset_type",
        "region",
        "last_price",
        "previous_close",
        "daily_change",
        "daily_change_pct",
        "five_day_change_pct",
        "one_month_change_pct",
        "status",
        "updated_at",
    ],
    "RiskMetrics": [
        "day",
        "symbol",
        "name",
        "region",
        "risk_level",
        "volatility_30d",
        "volatility_90d",
        "sharpe_90d",
        "max_drawdown_252d",
        "beta_vs_sp500",
        "notes",
        "updated_at",
    ],
    "NewsItems": [
        "day",
        "query",
        "title",
        "source",
        "link",
        "published",
        "updated_at",
    ],
}


def _clip(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    text = str(value)
    if len(text) > MAX_CELL_CHARS:
        return text[:MAX_CELL_CHARS] + "\n[truncated]"
    return text


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


def _replace_by_day(
    service,
    spreadsheet_id: str,
    title: str,
    headers: list[str],
    day: str,
    new_rows: Iterable[list[object]],
) -> None:
    existing = _values(service, spreadsheet_id, title)
    rows = existing[1:] if existing else []
    day_index = headers.index("day")
    kept_rows = [row for row in rows if len(row) <= day_index or row[day_index] != day]
    _write_values(
        service,
        spreadsheet_id,
        title,
        [headers] + kept_rows + [[_clip(value) for value in row] for row in new_rows],
    )


def _replace_all(
    service,
    spreadsheet_id: str,
    title: str,
    headers: list[str],
    rows: Iterable[list[object]],
) -> None:
    _write_values(
        service,
        spreadsheet_id,
        title,
        [headers] + [[_clip(value) for value in row] for row in rows],
    )


def fetch_tracked_keywords_from_sheet(spreadsheet_id: str) -> list[dict]:
    service = _service()
    _ensure_sheets(service, spreadsheet_id)
    rows = _values(service, spreadsheet_id, "KeywordWeights")
    if len(rows) < 2:
        return []
    headers = rows[0]
    results: list[dict] = []
    for row in rows[1:]:
        item = {
            header: row[index] if index < len(row) else ""
            for index, header in enumerate(headers)
        }
        if item.get("term"):
            results.append(item)
    return results


def _ensure_sheets(service, spreadsheet_id: str) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_titles = {
        sheet["properties"]["title"]
        for sheet in spreadsheet.get("sheets", [])
    }
    requests = [
        {"addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": 1000, "columnCount": 26}}}}
        for title in SHEETS
        if title not in existing_titles
    ]
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    for title, headers in SHEETS.items():
        first_row = _values(service, spreadsheet_id, title)[:1]
        if not first_row or first_row[0][: len(headers)] != headers:
            rows = _values(service, spreadsheet_id, title)
            _write_values(service, spreadsheet_id, title, [headers] + rows[1:])


def _service():
    credentials, _ = google.auth.default(scopes=SCOPES)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def export_daily_run_to_sheet(
    *,
    spreadsheet_id: str,
    day: str,
    report_path: str,
    report_markdown: str,
    ai_report: str | None,
    sheet_monitor_sync: str,
    sheet_keyword_seed: str,
    snapshots: list[MarketSnapshot],
    news_items: list[NewsItem],
    risk_metrics: list[RiskMetrics],
    keyword_scores: list[tuple[str, float]],
    tracked_keywords: list[dict],
) -> None:
    service = _service()
    _ensure_sheets(service, spreadsheet_id)
    updated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    _replace_by_day(
        service,
        spreadsheet_id,
        "DailyReports",
        SHEETS["DailyReports"],
        day,
        [
            [
                day,
                updated_at,
                report_path,
                len(news_items),
                len(snapshots),
                len(risk_metrics),
                sheet_monitor_sync,
                sheet_keyword_seed,
                ai_report or "",
                report_markdown,
            ]
        ],
    )

    _replace_all(
        service,
        spreadsheet_id,
        "KeywordWeights",
        SHEETS["KeywordWeights"],
        [
            [
                item.get("term", ""),
                item.get("weight", ""),
                item.get("first_seen_day", ""),
                item.get("last_seen_day", ""),
                item.get("appearances", ""),
                item.get("updated_at", ""),
            ]
            for item in tracked_keywords
        ],
    )

    _replace_by_day(
        service,
        spreadsheet_id,
        "KeywordTrends",
        SHEETS["KeywordTrends"],
        day,
        [[day, term, score, updated_at] for term, score in keyword_scores],
    )

    _replace_by_day(
        service,
        spreadsheet_id,
        "MarketSnapshots",
        SHEETS["MarketSnapshots"],
        day,
        [
            [
                day,
                snapshot.symbol,
                snapshot.name,
                snapshot.asset_type,
                snapshot.region,
                snapshot.last_price,
                snapshot.previous_close,
                snapshot.daily_change,
                snapshot.daily_change_pct,
                snapshot.five_day_change_pct,
                snapshot.one_month_change_pct,
                snapshot.status,
                updated_at,
            ]
            for snapshot in snapshots
        ],
    )

    _replace_by_day(
        service,
        spreadsheet_id,
        "RiskMetrics",
        SHEETS["RiskMetrics"],
        day,
        [
            [
                day,
                item.symbol,
                item.name,
                item.region,
                item.risk_level,
                item.volatility_30d,
                item.volatility_90d,
                item.sharpe_90d,
                item.max_drawdown_252d,
                item.beta_vs_sp500,
                "; ".join(item.notes),
                updated_at,
            ]
            for item in risk_metrics
        ],
    )

    _replace_by_day(
        service,
        spreadsheet_id,
        "NewsItems",
        SHEETS["NewsItems"],
        day,
        [
            [
                day,
                item.query,
                item.title,
                item.source,
                item.link,
                item.published or "",
                updated_at,
            ]
            for item in news_items
        ],
    )
