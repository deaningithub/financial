from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo


def today_string(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def execution_run_id(day: str, timezone: str) -> str:
    timestamp = datetime.now(ZoneInfo(timezone)).strftime("%Y%m%dT%H%M%S%f")
    return f"{day}_{timestamp}_{uuid4().hex[:8]}"
