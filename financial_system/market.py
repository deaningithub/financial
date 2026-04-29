from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import math

import yfinance as yf

from financial_system.config import DATA_DIR


@dataclass
class MarketSnapshot:
    symbol: str
    name: str
    asset_type: str
    region: str
    last_price: float | None
    previous_close: float | None
    daily_change: float | None
    daily_change_pct: float | None
    five_day_change_pct: float | None
    one_month_change_pct: float | None
    status: str


def configure_yfinance_cache() -> None:
    cache_dir = DATA_DIR / "yfinance_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass


def _clean(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def _status(change_pct: float | None) -> str:
    if change_pct is None:
        return "unknown"
    if change_pct >= 2:
        return "strong_up"
    if change_pct >= 0.5:
        return "up"
    if change_pct <= -2:
        return "strong_down"
    if change_pct <= -0.5:
        return "down"
    return "flat"


def fetch_market_snapshot(symbol_config: dict) -> MarketSnapshot:
    configure_yfinance_cache()
    symbol = symbol_config["symbol"]
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="2mo", interval="1d", auto_adjust=False)

    if history.empty:
        return MarketSnapshot(
            symbol=symbol,
            name=symbol_config.get("name", symbol),
            asset_type=symbol_config.get("type", "unknown"),
            region=symbol_config.get("region", "unknown"),
            last_price=None,
            previous_close=None,
            daily_change=None,
            daily_change_pct=None,
            five_day_change_pct=None,
            one_month_change_pct=None,
            status="missing_data",
        )

    closes = history["Close"].dropna()
    last = _clean(closes.iloc[-1]) if len(closes) else None
    previous = _clean(closes.iloc[-2]) if len(closes) > 1 else None
    five_day_previous = _clean(closes.iloc[-6]) if len(closes) > 5 else None
    month_previous = _clean(closes.iloc[-22]) if len(closes) > 21 else None
    daily_change = None if last is None or previous is None else last - previous
    daily_change_pct = _pct_change(last, previous)

    return MarketSnapshot(
        symbol=symbol,
        name=symbol_config.get("name", symbol),
        asset_type=symbol_config.get("type", "unknown"),
        region=symbol_config.get("region", "unknown"),
        last_price=last,
        previous_close=previous,
        daily_change=daily_change,
        daily_change_pct=daily_change_pct,
        five_day_change_pct=_pct_change(last, five_day_previous),
        one_month_change_pct=_pct_change(last, month_previous),
        status=_status(daily_change_pct),
    )


def fetch_market_snapshots(symbols: list[dict]) -> list[MarketSnapshot]:
    return [fetch_market_snapshot(symbol) for symbol in symbols]


def save_market_snapshots(path: Path, snapshots: list[MarketSnapshot]) -> None:
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "snapshots": [asdict(snapshot) for snapshot in snapshots],
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")


class MarketDataCollector:
    """Small async-compatible wrapper for cached market snapshots."""

    def __init__(self):
        self.symbols_config = [
            {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock", "region": "US"},
            {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "stock", "region": "US"},
            {"symbol": "2330.TW", "name": "Taiwan Semiconductor", "type": "stock", "region": "TW"},
            {"symbol": "^GSPC", "name": "S&P 500", "type": "index", "region": "US"},
            {"symbol": "^VIX", "name": "VIX Volatility Index", "type": "index", "region": "US"},
        ]

    async def initialize(self):
        """Prepare local yfinance cache storage."""
        configure_yfinance_cache()

    async def collect_all_data(self):
        """Collect configured market snapshots into the latest snapshot file."""
        snapshots = fetch_market_snapshots(self.symbols_config)
        save_market_snapshots(DATA_DIR / "latest_snapshots.json", snapshots)
        return snapshots

    async def get_latest_snapshots(self) -> list[MarketSnapshot]:
        """Load the latest cached market snapshots."""
        try:
            snapshots_path = DATA_DIR / "latest_snapshots.json"
            if snapshots_path.exists():
                with snapshots_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [MarketSnapshot(**s) for s in data.get("snapshots", [])]
        except Exception:
            pass
        return []

    async def get_top_movers(self) -> list[dict]:
        """Return the largest cached daily market moves."""
        snapshots = await self.get_latest_snapshots()
        movers = []

        for snapshot in snapshots:
            if snapshot.daily_change_pct and abs(snapshot.daily_change_pct) > 2:
                movers.append({
                    "symbol": snapshot.symbol,
                    "name": snapshot.name,
                    "change_pct": snapshot.daily_change_pct,
                    "price": snapshot.last_price,
                    "direction": "up" if snapshot.daily_change_pct > 0 else "down"
                })

        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return movers[:10]

    async def get_latest_news(self) -> list[dict]:
        """Return a minimal placeholder for callers that expect latest news."""
        return [
            {
                "title": "Market Update",
                "summary": "Daily market summary",
                "timestamp": datetime.now().isoformat(),
                "sentiment": "neutral"
            }
        ]
