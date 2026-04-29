from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def today_string(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).date().isoformat()
