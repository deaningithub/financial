from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import math

import yfinance as yf

from financial_system.market import MarketSnapshot, configure_yfinance_cache


@dataclass
class RiskMetrics:
    symbol: str
    name: str
    region: str
    day: str
    volatility_30d: float | None
    volatility_90d: float | None
    sharpe_90d: float | None
    max_drawdown_252d: float | None
    beta_vs_sp500: float | None
    risk_level: str
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _clean_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _annualized_volatility(returns, window: int) -> float | None:
    series = returns.dropna().tail(window)
    if len(series) < max(10, window // 2):
        return None
    return _clean_number(series.std() * math.sqrt(252) * 100)


def _sharpe_ratio(returns, risk_free_rate: float = 0.02) -> float | None:
    series = returns.dropna().tail(90)
    if len(series) < 30:
        return None
    excess_daily = series - (risk_free_rate / 252)
    std = excess_daily.std()
    if not std:
        return None
    return _clean_number((excess_daily.mean() / std) * math.sqrt(252))


def _max_drawdown(close) -> float | None:
    series = close.dropna().tail(252)
    if len(series) < 30:
        return None
    peak = series.cummax()
    drawdown = (series / peak) - 1
    return _clean_number(drawdown.min() * 100)


def _beta(symbol_returns, benchmark_returns) -> float | None:
    frame = symbol_returns.to_frame("symbol").join(benchmark_returns.to_frame("benchmark"), how="inner").dropna()
    if len(frame) < 30:
        return None
    benchmark_variance = frame["benchmark"].var()
    if not benchmark_variance:
        return None
    covariance = frame["symbol"].cov(frame["benchmark"])
    return _clean_number(covariance / benchmark_variance)


def _risk_level(
    daily_change_pct: float | None,
    volatility_30d: float | None,
    max_drawdown_252d: float | None,
    beta_vs_sp500: float | None,
) -> tuple[str, list[str]]:
    score = 0
    notes: list[str] = []

    if daily_change_pct is not None and abs(daily_change_pct) >= 3:
        score += 2
        notes.append(f"Large daily move: {daily_change_pct:.2f}%")
    elif daily_change_pct is not None and abs(daily_change_pct) >= 1.5:
        score += 1
        notes.append(f"Elevated daily move: {daily_change_pct:.2f}%")

    if volatility_30d is not None and volatility_30d >= 45:
        score += 2
        notes.append(f"High 30-day volatility: {volatility_30d:.2f}%")
    elif volatility_30d is not None and volatility_30d >= 25:
        score += 1
        notes.append(f"Elevated 30-day volatility: {volatility_30d:.2f}%")

    if max_drawdown_252d is not None and max_drawdown_252d <= -25:
        score += 2
        notes.append(f"Deep 252-day drawdown: {max_drawdown_252d:.2f}%")
    elif max_drawdown_252d is not None and max_drawdown_252d <= -12:
        score += 1
        notes.append(f"Meaningful 252-day drawdown: {max_drawdown_252d:.2f}%")

    if beta_vs_sp500 is not None and abs(beta_vs_sp500) >= 1.5:
        score += 1
        notes.append(f"High beta versus S&P 500: {beta_vs_sp500:.2f}")

    if score >= 4:
        return "high", notes
    if score >= 2:
        return "medium", notes
    return "low", notes


def calculate_risk_metrics(
    snapshots: list[MarketSnapshot],
    day: str,
    benchmark_symbol: str = "^GSPC",
    max_symbols: int = 24,
) -> list[RiskMetrics]:
    configure_yfinance_cache()
    selected = [
        item
        for item in snapshots
        if item.last_price is not None and item.asset_type in {"stock", "index", "etf", "commodity", "crypto"}
    ][:max_symbols]
    if not selected:
        return []

    symbols = sorted({item.symbol for item in selected} | {benchmark_symbol})
    data = yf.download(
        symbols,
        period="1y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if data.empty or "Close" not in data:
        return []

    close = data["Close"].dropna(how="all")
    if close.empty:
        return []

    returns = close.pct_change(fill_method=None)
    benchmark_returns = returns[benchmark_symbol] if benchmark_symbol in returns else None
    metrics: list[RiskMetrics] = []

    for item in selected:
        if item.symbol not in close:
            continue
        symbol_close = close[item.symbol].dropna()
        symbol_returns = returns[item.symbol].dropna()
        if symbol_close.empty or len(symbol_returns) < 10:
            continue

        vol_30d = _annualized_volatility(symbol_returns, 30)
        vol_90d = _annualized_volatility(symbol_returns, 90)
        sharpe_90d = _sharpe_ratio(symbol_returns)
        drawdown = _max_drawdown(symbol_close)
        beta = _beta(symbol_returns, benchmark_returns) if benchmark_returns is not None else None
        level, notes = _risk_level(item.daily_change_pct, vol_30d, drawdown, beta)

        metrics.append(
            RiskMetrics(
                symbol=item.symbol,
                name=item.name,
                region=item.region,
                day=day,
                volatility_30d=vol_30d,
                volatility_90d=vol_90d,
                sharpe_90d=sharpe_90d,
                max_drawdown_252d=drawdown,
                beta_vs_sp500=beta,
                risk_level=level,
                notes=notes,
            )
        )

    return sorted(
        metrics,
        key=lambda item: (
            {"high": 3, "medium": 2, "low": 1}.get(item.risk_level, 0),
            abs(item.volatility_30d or 0),
        ),
        reverse=True,
    )


def format_risk_metrics(metrics: list[RiskMetrics], limit: int = 8) -> str:
    if not metrics:
        return "No risk metrics available."
    lines = []
    for item in metrics[:limit]:
        notes = "; ".join(item.notes) if item.notes else "No abnormal risk flags."
        lines.append(
            f"- {item.name} ({item.symbol}): risk={item.risk_level}, "
            f"30d_vol={_fmt(item.volatility_30d)}%, "
            f"max_drawdown={_fmt(item.max_drawdown_252d)}%, "
            f"beta={_fmt(item.beta_vs_sp500)}. {notes}"
        )
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


if __name__ == "__main__":
    print(f"Risk analyzer module loaded at {datetime.now().isoformat(timespec='seconds')}")
