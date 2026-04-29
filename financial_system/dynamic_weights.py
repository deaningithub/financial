from __future__ import annotations

from financial_system.market import MarketSnapshot


def _by_symbol(snapshots: list[MarketSnapshot]) -> dict[str, MarketSnapshot]:
    return {snapshot.symbol: snapshot for snapshot in snapshots}


def build_dynamic_condition_queries(
    snapshots: list[MarketSnapshot],
    max_queries: int = 8,
) -> list[str]:
    """Build short-term macro/market-condition queries from daily market state."""
    by_symbol = _by_symbol(snapshots)
    queries: list[str] = []

    vix = by_symbol.get("^VIX")
    if vix and vix.last_price is not None:
        if vix.last_price >= 20 or abs(vix.daily_change_pct or 0) >= 8:
            queries.append("market volatility risk global equities")
        elif vix.last_price <= 15:
            queries.append("low volatility complacency equity market risk")

    oil = by_symbol.get("CL=F")
    if oil and abs(oil.daily_change_pct or 0) >= 2:
        direction = "rising" if (oil.daily_change_pct or 0) > 0 else "falling"
        queries.append(f"{direction} oil prices inflation market impact")

    dollar = by_symbol.get("DX-Y.NYB")
    if dollar and abs(dollar.five_day_change_pct or 0) >= 1:
        direction = "stronger" if (dollar.five_day_change_pct or 0) > 0 else "weaker"
        queries.append(f"{direction} US dollar global stocks impact")

    ten_year = by_symbol.get("^TNX")
    if ten_year and abs(ten_year.five_day_change_pct or 0) >= 2:
        direction = "higher" if (ten_year.five_day_change_pct or 0) > 0 else "lower"
        queries.append(f"{direction} treasury yields growth stocks impact")

    regional_indexes = [
        "^GSPC",
        "^TWII",
        "^STOXX50E",
        "000001.SS",
        "^HSI",
        "^N225",
        "^BSESN",
        "^NSEI",
    ]
    for symbol in regional_indexes:
        snapshot = by_symbol.get(symbol)
        if not snapshot or abs(snapshot.daily_change_pct or 0) < 1.5:
            continue
        direction = "rally" if (snapshot.daily_change_pct or 0) > 0 else "selloff"
        queries.append(f"{snapshot.name} {direction} reason today")
        if len(queries) >= max_queries:
            break

    return queries[:max_queries]
