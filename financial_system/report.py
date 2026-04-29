from __future__ import annotations

from pathlib import Path
from collections import defaultdict

from financial_system.market import MarketSnapshot
from financial_system.news import NewsItem


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def _append_snapshot_table(lines: list[str], snapshots: list[MarketSnapshot]) -> None:
    lines.extend(["| Name | Symbol | Price | Daily | 5D | 1M | Status |", "| --- | --- | ---: | ---: | ---: | ---: | --- |"])
    for item in snapshots:
        price = "n/a" if item.last_price is None else f"{item.last_price:.2f}"
        lines.append(
            f"| {item.name} | {item.symbol} | {price} | {_format_pct(item.daily_change_pct)} | "
            f"{_format_pct(item.five_day_change_pct)} | {_format_pct(item.one_month_change_pct)} | {item.status} |"
        )


def render_report(
    day: str,
    notes: str,
    snapshots: list[MarketSnapshot],
    movers: list[MarketSnapshot],
    news_items: list[NewsItem],
    ai_report: str | None,
) -> str:
    lines = [
        f"# Daily Financial Report - {day}",
        "",
        "## Manual Notes",
        notes.strip() or "No manual notes provided.",
        "",
        "## Biggest Movers",
        "| Name | Symbol | Daily | 5D | 1M | Status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for mover in movers:
        lines.append(
            f"| {mover.name} | {mover.symbol} | {_format_pct(mover.daily_change_pct)} | "
            f"{_format_pct(mover.five_day_change_pct)} | {_format_pct(mover.one_month_change_pct)} | "
            f"{mover.status} |"
        )

    lines.extend(["", "## Market Snapshot"])
    by_region: dict[str, list[MarketSnapshot]] = defaultdict(list)
    for item in snapshots:
        by_region[item.region].append(item)

    for region in sorted(by_region):
        lines.extend(["", f"### {region}"])
        _append_snapshot_table(lines, by_region[region])

    lines.extend(["", "## Related News"])
    if news_items:
        for item in news_items:
            lines.append(f"- [{item.query}] [{item.title}]({item.link}) - {item.source}")
    else:
        lines.append("No related news collected.")

    lines.extend(["", "## AI Summary And Risk Assessment"])
    lines.append(ai_report or "OpenAI summary skipped. Add OPENAI_API_KEY to enable it.")
    lines.extend(["", "_This report is for research and is not financial advice._", ""])
    return "\n".join(lines)


def save_report(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
