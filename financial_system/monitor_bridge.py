from __future__ import annotations

from dataclasses import asdict, dataclass


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


def format_monitor_events(events: list[MonitorEvent]) -> str:
    if not events:
        return "No external monitor events available."
    lines = []
    for event in events:
        symbol = f" ({event.symbol})" if event.symbol else ""
        lines.append(
            f"- [{event.severity}] {event.title}{symbol}; "
            f"type={event.event_type}; source={event.source}; time={event.event_time}"
        )
    return "\n".join(lines)
