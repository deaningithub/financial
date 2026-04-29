from __future__ import annotations

from dataclasses import dataclass

from financial_system.market import MarketSnapshot


@dataclass
class TrendAlert:
    trend: str
    symbol: str
    name: str
    reason: str
    daily_change_pct: float | None
    five_day_change_pct: float | None
    one_month_change_pct: float | None
    keywords: list[str]


def _crossed(value: float | None, threshold: float) -> bool:
    return value is not None and abs(value) >= threshold


def evaluate_long_term_trends(
    trend_config: dict,
    snapshots: list[MarketSnapshot],
) -> list[TrendAlert]:
    by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}
    alerts: list[TrendAlert] = []
    for trend, config in trend_config.items():
        daily_threshold = float(config.get("daily_threshold_pct", 2.5))
        five_day_threshold = float(config.get("five_day_threshold_pct", 8.0))
        one_month_threshold = float(config.get("one_month_threshold_pct", 18.0))
        keywords = list(config.get("keywords", []))
        for symbol in config.get("symbols", []):
            snapshot = by_symbol.get(symbol)
            if snapshot is None:
                continue
            reasons = []
            if _crossed(snapshot.daily_change_pct, daily_threshold):
                reasons.append(f"daily move {snapshot.daily_change_pct:.2f}%")
            if _crossed(snapshot.five_day_change_pct, five_day_threshold):
                reasons.append(f"5-day move {snapshot.five_day_change_pct:.2f}%")
            if _crossed(snapshot.one_month_change_pct, one_month_threshold):
                reasons.append(f"1-month move {snapshot.one_month_change_pct:.2f}%")
            if not reasons:
                continue
            alerts.append(
                TrendAlert(
                    trend=trend,
                    symbol=snapshot.symbol,
                    name=snapshot.name,
                    reason=", ".join(reasons),
                    daily_change_pct=snapshot.daily_change_pct,
                    five_day_change_pct=snapshot.five_day_change_pct,
                    one_month_change_pct=snapshot.one_month_change_pct,
                    keywords=keywords,
                )
            )
    return alerts


def build_long_term_trend_queries(
    alerts: list[TrendAlert],
    max_queries: int = 6,
) -> list[str]:
    queries: list[str] = []
    for alert in alerts:
        if len(queries) >= max_queries:
            break
        base_keyword = alert.keywords[0] if alert.keywords else alert.trend
        queries.append(f"{alert.name} {base_keyword} trend stock impact")
        if len(queries) >= max_queries:
            break
        queries.append(f"{alert.trend} {alert.reason} market impact")
    return queries[:max_queries]


def format_trend_alerts(alerts: list[TrendAlert]) -> str:
    if not alerts:
        return "No long-term trend monitor crossed its attention threshold today."
    lines = []
    for alert in alerts:
        lines.append(
            f"- {alert.trend}: {alert.name} ({alert.symbol}) triggered attention because {alert.reason}."
        )
    return "\n".join(lines)
