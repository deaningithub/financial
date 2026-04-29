from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from financial_system.market import configure_yfinance_cache


@dataclass
class CorrelationResult:
    left: str
    right: str
    label: str
    correlation: float | None
    observations: int
    status: str


def _extract_close_frame(data):
    if data is None or data.empty:
        return None
    if "Close" in data:
        close = data["Close"]
    elif ("Close" in data.columns.get_level_values(0)):
        close = data["Close"]
    else:
        return None
    if hasattr(close, "dropna"):
        return close.dropna(how="all")
    return None


def compute_cross_market_correlations(
    pairs: list[dict],
    lookback_days: int = 90,
    min_abs_correlation: float = 0.45,
) -> list[CorrelationResult]:
    symbols = sorted({item["left"] for item in pairs} | {item["right"] for item in pairs})
    if not symbols:
        return []

    configure_yfinance_cache()
    data = yf.download(
        symbols,
        period=f"{lookback_days}d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    closes = _extract_close_frame(data)
    if closes is None or closes.empty:
        return [
            CorrelationResult(
                left=item["left"],
                right=item["right"],
                label=item.get("label", f"{item['left']} vs {item['right']}"),
                correlation=None,
                observations=0,
                status="missing_data",
            )
            for item in pairs
        ]

    returns = closes.pct_change(fill_method=None).dropna(how="all")
    results: list[CorrelationResult] = []
    for item in pairs:
        left = item["left"]
        right = item["right"]
        label = item.get("label", f"{left} vs {right}")
        if left not in returns or right not in returns:
            results.append(CorrelationResult(left, right, label, None, 0, "missing_pair"))
            continue
        frame = returns[[left, right]].dropna()
        observations = len(frame)
        if observations < 10:
            results.append(CorrelationResult(left, right, label, None, observations, "insufficient_data"))
            continue
        correlation = float(frame[left].corr(frame[right]))
        if abs(correlation) >= min_abs_correlation:
            status = "strong_positive" if correlation > 0 else "strong_negative"
        else:
            status = "weak_or_mixed"
        results.append(CorrelationResult(left, right, label, correlation, observations, status))
    return results


def format_correlations(results: list[CorrelationResult]) -> str:
    if not results:
        return "No cross-market correlation analysis available."
    lines = []
    for result in results:
        if result.correlation is None:
            lines.append(f"- {result.label}: {result.status} ({result.observations} observations)")
            continue
        lines.append(
            f"- {result.label}: corr={result.correlation:.2f}, "
            f"observations={result.observations}, status={result.status}"
        )
    return "\n".join(lines)
