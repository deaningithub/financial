from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from financial_system.monitor_bridge import MonitorEvent


REQUIRED_COLUMNS = {
    "id",
    "source",
    "event_type",
    "severity",
    "event_time",
    "title",
}


@dataclass
class SheetSyncResult:
    imported: int
    skipped: int
    source_url: str


def google_sheet_csv_url(sheet_url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        raise ValueError("Invalid Google Sheet URL. Expected a /spreadsheets/d/<id>/ URL.")
    spreadsheet_id = match.group(1)
    query = parse_qs(urlparse(sheet_url).query)
    gid = (query.get("gid") or ["0"])[0]
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


def parse_monitor_events_csv(csv_text: str) -> tuple[list[MonitorEvent], int]:
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames:
        return [], 0
    headers = {header.strip() for header in reader.fieldnames if header}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise ValueError(f"Monitor sheet is missing required columns: {', '.join(sorted(missing))}")

    events: list[MonitorEvent] = []
    skipped = 0
    for row in reader:
        event_id = (row.get("id") or "").strip()
        title = (row.get("title") or "").strip()
        event_time = (row.get("event_time") or "").strip()
        if not event_id or not title or not event_time:
            skipped += 1
            continue
        payload = {
            key: value
            for key, value in row.items()
            if key not in {"id", "source", "event_type", "symbol", "severity", "event_time", "title"}
            and value not in (None, "")
        }
        events.append(
            MonitorEvent(
                id=event_id,
                source=(row.get("source") or "google-sheet").strip(),
                event_type=(row.get("event_type") or "external_event").strip(),
                symbol=(row.get("symbol") or "").strip() or None,
                title=title,
                severity=(row.get("severity") or "medium").strip().lower(),
                event_time=event_time,
                payload=payload,
            )
        )
    return events, skipped


def fetch_monitor_events_from_sheet(sheet_url: str, timeout_seconds: int = 20) -> tuple[list[MonitorEvent], int]:
    csv_url = google_sheet_csv_url(sheet_url)
    with urlopen(csv_url, timeout=timeout_seconds) as response:
        csv_text = response.read().decode("utf-8-sig")
    return parse_monitor_events_csv(csv_text)
