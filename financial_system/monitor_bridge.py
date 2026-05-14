from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import re


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class MonitorEvent:
    id: str
    source: str
    event_type: str
    symbol: str | None
    title: str
    severity: str
    event_time: str
    payload: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_event_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _event_day(event: MonitorEvent) -> str:
    try:
        parsed = datetime.fromisoformat(event.event_time.replace("Z", "+00:00"))
    except ValueError:
        return event.event_time[:10]
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None) + timedelta(hours=8)
    return parsed.date().isoformat()


def _short_symbol(symbol: str | None) -> str:
    if not symbol:
        return ""
    return symbol.split(":")[-1].upper()


def _event_direction(event: MonitorEvent, move_pct: float | None) -> str:
    if move_pct is not None:
        if move_pct > 0:
            return "up"
        if move_pct < 0:
            return "down"
    title = event.title.lower()
    if "above" in title or " up" in title:
        return "up"
    if "below" in title or " down" in title:
        return "down"
    return "neutral"


def _canonical_event_type(event: MonitorEvent) -> str:
    value = event.event_type.lower()
    title = event.title.lower()
    if "intraday" in value or "intraday" in title:
        return "intraday_move"
    if "daily" in value or "daily move" in title or value in {"price_alert", "price_move_alert"}:
        return "daily_move"
    if "price_above" in value or "crossed above" in title:
        return "price_above"
    if "price_below" in value or "crossed below" in title:
        return "price_below"
    return value or "external_event"


def _float_from_payload(event: MonitorEvent, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = event.payload.get(key)
        if value in (None, ""):
            continue
        try:
            return float(str(value).replace("%", ""))
        except ValueError:
            continue
    return None


def _move_pct(event: MonitorEvent) -> float | None:
    event_type = _canonical_event_type(event)
    if event_type == "intraday_move":
        value = _float_from_payload(event, ("intraday_change_pct", "intradayChangePct", "daily_change_pct"))
    elif event_type == "daily_move":
        value = _float_from_payload(event, ("daily_change_pct", "dailyChangePct", "change_pct"))
    else:
        value = _float_from_payload(event, ("daily_change_pct", "intraday_change_pct", "change_pct"))
    if value is not None:
        return value
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", event.title)
    return float(match.group(1)) if match else None


def _threshold(event: MonitorEvent) -> float | None:
    value = _float_from_payload(event, ("threshold", "price_above", "price_below"))
    if value is not None:
        return value
    match = re.search(r"(?:above|below)\s+([-+]?\d+(?:\.\d+)?)", event.title.lower())
    return float(match.group(1)) if match else None


def _severity_for_move(event_type: str, move_abs: float | None, original: str) -> str:
    if move_abs is None:
        return original if original in SEVERITY_RANK else "medium"
    if event_type == "intraday_move":
        if move_abs >= 3.5:
            return "critical"
        if move_abs >= 2.0:
            return "high"
        if move_abs >= 1.0:
            return "medium"
        return "low"
    if event_type == "daily_move":
        if move_abs >= 5.0:
            return "critical"
        if move_abs >= 3.0:
            return "high"
        if move_abs >= 1.5:
            return "medium"
        return "low"
    return original if original in SEVERITY_RANK else "medium"


def _is_noise(event: MonitorEvent, event_type: str) -> bool:
    if event_type in {"price_above", "price_below"}:
        threshold = _threshold(event)
        price = _float_from_payload(event, ("price",))
        if threshold is None:
            return True
        if threshold <= 1:
            return True
        if price and threshold < price * 0.5:
            return True
    return False


def _normalized_copy(event: MonitorEvent) -> MonitorEvent:
    event_type = _canonical_event_type(event)
    move = _move_pct(event)
    severity = _severity_for_move(event_type, abs(move) if move is not None else None, event.severity.lower())
    payload = dict(event.payload)
    payload["normalized_event_type"] = event_type
    if move is not None:
        payload["normalized_move_pct"] = move
    return MonitorEvent(
        id=event.id,
        source=event.source,
        event_type=event.event_type,
        symbol=event.symbol,
        title=event.title,
        severity=severity,
        event_time=event.event_time,
        payload=payload,
    )


def dedupe_monitor_events(events: list[MonitorEvent]) -> tuple[list[MonitorEvent], dict[str, int]]:
    """Collapse repeated monitor alerts before they reach the report."""
    kept: dict[tuple[str, str, str, str], MonitorEvent] = {}
    stats = {"input": len(events), "noise": 0, "duplicates": 0, "low": 0}

    for raw_event in events:
        event = _normalized_copy(raw_event)
        event_type = str(event.payload.get("normalized_event_type") or _canonical_event_type(event))
        move = event.payload.get("normalized_move_pct")
        move_float = float(move) if isinstance(move, (int, float)) else _move_pct(event)
        if _is_noise(event, event_type):
            stats["noise"] += 1
            continue
        if event.severity == "low":
            stats["low"] += 1
            continue

        key = (
            _event_day(event),
            _short_symbol(event.symbol),
            event_type,
            _event_direction(event, move_float),
        )
        existing = kept.get(key)
        if existing is None:
            kept[key] = event
            continue

        stats["duplicates"] += 1
        existing_move = _move_pct(existing)
        existing_score = (
            SEVERITY_RANK.get(existing.severity, 0),
            abs(existing_move or 0),
            _parse_event_time(existing.event_time),
        )
        event_score = (
            SEVERITY_RANK.get(event.severity, 0),
            abs(move_float or 0),
            _parse_event_time(event.event_time),
        )
        if event_score > existing_score:
            kept[key] = event

    deduped = sorted(kept.values(), key=lambda item: _parse_event_time(item.event_time), reverse=True)
    stats["output"] = len(deduped)
    return deduped, stats


def summarize_monitor_events(events: list[MonitorEvent], stats: dict[str, int] | None = None) -> str:
    if not events:
        if stats and stats.get("input"):
            return (
                f"External monitor bridge received {stats['input']} raw alerts, but all were duplicate, "
                "low-grade, or invalid threshold noise."
            )
        return "No external monitor events available."

    tech_moves = []
    for event in events:
        symbol = _short_symbol(event.symbol)
        move = _move_pct(event)
        event_type = str(event.payload.get("normalized_event_type") or _canonical_event_type(event))
        if symbol in {"AAPL", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "TSM"} and move is not None:
            label = "daily" if event_type == "daily_move" else "intraday" if event_type == "intraday_move" else event_type
            tech_moves.append(f"{symbol} {label} {move:+.2f}%")

    if tech_moves:
        summary = (
            "Monitor narrative: large-cap technology alerts point to a concentrated tech/AI signal: "
            + ", ".join(tech_moves[:6])
            + ". Confirm breadth with Nasdaq 100, semiconductor ETFs, VIX, yields, and TSMC ADR before treating it as broad risk appetite."
        )
    else:
        summary = "Monitor narrative: external alerts were consolidated into distinct reportable events."

    if stats:
        suppressed = stats.get("duplicates", 0) + stats.get("noise", 0) + stats.get("low", 0)
        if suppressed:
            summary += (
                f" Suppressed {suppressed} repeated or low-signal raw alerts "
                f"({stats.get('duplicates', 0)} duplicates, {stats.get('noise', 0)} invalid-threshold noise, {stats.get('low', 0)} low-grade moves)."
            )
    return summary


def format_monitor_events(events: list[MonitorEvent]) -> str:
    deduped, stats = dedupe_monitor_events(events)
    if not deduped:
        return summarize_monitor_events(deduped, stats)
    lines = [summarize_monitor_events(deduped, stats), ""]
    for event in deduped:
        symbol = f" ({event.symbol})" if event.symbol else ""
        lines.append(
            f"- [{event.severity}] {event.title}{symbol}; "
            f"type={event.event_type}; source={event.source}; time={event.event_time}"
        )
    return "\n".join(lines)
