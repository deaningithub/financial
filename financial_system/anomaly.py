from __future__ import annotations

from financial_system.market import MarketSnapshot


def rank_biggest_movers(
    snapshots: list[MarketSnapshot],
    limit: int = 7,
) -> list[MarketSnapshot]:
    valid = [
        snapshot
        for snapshot in snapshots
        if snapshot.daily_change_pct is not None
    ]
    return sorted(
        valid,
        key=lambda snapshot: abs(snapshot.daily_change_pct or 0),
        reverse=True,
    )[:limit]


def build_anomaly_queries(movers: list[MarketSnapshot]) -> list[str]:
    queries = []
    for mover in movers:
        direction = "rose" if (mover.daily_change_pct or 0) >= 0 else "fell"
        queries.append(f"why {mover.name} {direction} today {mover.symbol}")
    return queries
