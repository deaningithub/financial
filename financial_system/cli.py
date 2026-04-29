from __future__ import annotations

import argparse
from datetime import datetime
from types import SimpleNamespace

from financial_system.config import DATA_DIR, ensure_directories, load_trend_monitors, read_symbols, write_symbols
from financial_system.dates import today_string
from financial_system.config import load_settings
from financial_system.database import init_db, load_historical_keyword_scores, load_monitor_events, save_monitor_event, save_monitor_events
from financial_system.google_sheet_bridge import fetch_monitor_events_from_sheet
from financial_system.keywords import build_keyword_queries, build_policy_queries, blend_keywords, rank_keywords
from financial_system.monitor_bridge import MonitorEvent, format_monitor_events
from financial_system.notes import append_note
from financial_system.notes import read_notes
from financial_system.risk_analyzer import calculate_risk_metrics
from financial_system.market import fetch_market_snapshots


def _cmd_add_note(args: argparse.Namespace) -> None:
    ensure_directories()
    settings = load_settings()
    day = args.date or today_string(settings.timezone)
    path = append_note(DATA_DIR / "manual_notes", day, args.text)
    print(f"Saved note to {path}")


def _cmd_run(args: argparse.Namespace) -> None:
    from financial_system.pipeline import run_daily_pipeline

    outputs = run_daily_pipeline(day=args.date, use_ai=not args.no_ai)
    print("Daily financial report created:")
    for label, path in outputs.items():
        print(f"- {label}: {path}")


def _cmd_symbols(_: argparse.Namespace) -> None:
    for item in read_symbols():
        print(f"{item['symbol']}: {item.get('name', item['symbol'])} [{item.get('type', 'unknown')}]")


def _cmd_add_symbol(args: argparse.Namespace) -> None:
    symbols = read_symbols()
    if any(item["symbol"].upper() == args.symbol.upper() for item in symbols):
        raise SystemExit(f"{args.symbol} already exists in config/symbols.json")
    symbols.append(
        {
            "symbol": args.symbol,
            "name": args.name,
            "type": args.type,
            "region": args.region,
        }
    )
    write_symbols(symbols)
    print(f"Added {args.symbol} to config/symbols.json")


def _cmd_inspect_keywords(args: argparse.Namespace) -> None:
    settings = load_settings()
    day = args.date or today_string(settings.timezone)
    text = args.text if args.text is not None else read_notes(DATA_DIR / "manual_notes", day)
    ranked = rank_keywords(text, limit=args.limit or settings.keyword_limit)
    init_db()
    historical_scores = load_historical_keyword_scores(
        max_days=settings.keyword_retention_days,
        decay=settings.keyword_decay_factor,
        min_score=settings.keyword_min_score,
        exclude_days={day},
    )
    primary_keywords, secondary_keywords = blend_keywords(
        ranked,
        historical_scores,
        primary_limit=args.limit or settings.keyword_limit,
        secondary_limit=args.secondary_limit or settings.keyword_secondary_limit,
    )
    primary_queries = build_keyword_queries(primary_keywords, max_queries=args.query_limit or settings.keyword_query_limit)
    secondary_queries = build_keyword_queries(secondary_keywords, max_queries=args.secondary_limit or settings.keyword_secondary_limit)
    symbol_snapshots = [
        SimpleNamespace(
            symbol=item["symbol"],
        )
        for item in read_symbols()
    ]
    policy_queries = build_policy_queries(
        symbol_snapshots,
        policy_limit=args.policy_limit or settings.policy_query_limit,
        company_limit=args.policy_company_limit or settings.policy_company_query_limit,
    )
    trend_monitors = load_trend_monitors()

    print(f"Keyword source date: {day}")
    if not ranked:
        print("No keywords found.")
    else:
        print("Ranked primary candidates:")
        for keyword, score in ranked:
            print(f"- {keyword}: {score}")

    print("Primary search queries:")
    for query in primary_queries:
        print(f"- {query}")

    if secondary_keywords:
        print("Secondary historical keywords:")
        for keyword in secondary_keywords:
            print(f"- {keyword}: {historical_scores[keyword]:.2f}")
        print("Secondary search queries:")
        for query in secondary_queries:
            print(f"- {query}")

    if policy_queries:
        print("Policy search queries:")
        for query in policy_queries:
            print(f"- {query}")

    if trend_monitors:
        print("Long-term trend monitors:")
        for trend, config in trend_monitors.items():
            symbols = ", ".join(config.get("symbols", []))
            print(
                f"- {trend}: symbols={symbols}; "
                f"daily>={config.get('daily_threshold_pct')}%, "
                f"5d>={config.get('five_day_threshold_pct')}%, "
                f"1m>={config.get('one_month_threshold_pct')}%"
            )


def _cmd_risk(args: argparse.Namespace) -> None:
    settings = load_settings()
    day = args.date or today_string(settings.timezone)
    symbols = read_symbols()
    if args.symbols:
        wanted = {symbol.upper() for symbol in args.symbols}
        symbols = [item for item in symbols if item["symbol"].upper() in wanted]
    snapshots = fetch_market_snapshots(symbols)
    metrics = calculate_risk_metrics(snapshots, day=day, max_symbols=args.limit)
    if not metrics:
        print("No risk metrics available. Market data may be missing or the data source may be unavailable.")
        return
    for item in metrics:
        notes = "; ".join(item.notes) if item.notes else "No abnormal risk flags."
        print(
            f"{item.symbol}: risk={item.risk_level}, "
            f"30d_vol={_fmt_number(item.volatility_30d)}%, "
            f"90d_vol={_fmt_number(item.volatility_90d)}%, "
            f"max_drawdown={_fmt_number(item.max_drawdown_252d)}%, "
            f"beta={_fmt_number(item.beta_vs_sp500)} | {notes}"
        )


def _fmt_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _cmd_monitor_events(args: argparse.Namespace) -> None:
    init_db()
    if args.sync_sheet:
        settings = load_settings()
        sheet_url = args.sheet_url or settings.google_sheet_monitor_url
        if not sheet_url:
            raise SystemExit("No Google Sheet URL provided. Set GOOGLE_SHEET_MONITOR_URL or pass --sheet-url.")
        events, skipped = fetch_monitor_events_from_sheet(sheet_url)
        imported = save_monitor_events(events)
        print(f"Synced monitor events from Google Sheet: imported={imported}, skipped={skipped}")
        return

    if args.add_sample:
        event = MonitorEvent(
            id=args.add_sample,
            source="manual-cli",
            event_type="sample_alert",
            symbol=args.symbol,
            title=args.title or "Sample external monitor event",
            severity=args.severity,
            event_time=args.event_time,
            payload={"note": "Inserted through CLI for SQLite bridge testing."},
        )
        save_monitor_event(event)
        print(f"Saved monitor event: {event.id}")
        return

    settings = load_settings()
    events = load_monitor_events(
        lookback_hours=args.lookback_hours or settings.monitor_event_lookback_hours,
        limit=args.limit or settings.monitor_event_limit,
    )
    print(format_monitor_events(events))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily financial intelligence system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_note = subparsers.add_parser("add-note", help="Add manual news or keyword notes")
    add_note.add_argument("--text", required=True)
    add_note.add_argument("--date")
    add_note.set_defaults(func=_cmd_add_note)

    run = subparsers.add_parser("run", help="Run the daily pipeline")
    run.add_argument("--date")
    run.add_argument("--no-ai", action="store_true")
    run.set_defaults(func=_cmd_run)

    symbols = subparsers.add_parser("symbols", help="List configured market symbols")
    symbols.set_defaults(func=_cmd_symbols)

    add_symbol = subparsers.add_parser("add-symbol", help="Add a market symbol")
    add_symbol.add_argument("--symbol", required=True)
    add_symbol.add_argument("--name", required=True)
    add_symbol.add_argument("--type", default="stock")
    add_symbol.add_argument("--region", default="US")
    add_symbol.set_defaults(func=_cmd_add_symbol)

    inspect_keywords = subparsers.add_parser("inspect-keywords", help="Show weighted keywords and derived search queries")
    inspect_keywords.add_argument("--text")
    inspect_keywords.add_argument("--date")
    inspect_keywords.add_argument("--limit", type=int)
    inspect_keywords.add_argument("--query-limit", type=int)
    inspect_keywords.add_argument("--secondary-limit", type=int)
    inspect_keywords.add_argument("--policy-limit", type=int)
    inspect_keywords.add_argument("--policy-company-limit", type=int)
    inspect_keywords.set_defaults(func=_cmd_inspect_keywords)

    risk = subparsers.add_parser("risk", help="Calculate current risk metrics")
    risk.add_argument("--date")
    risk.add_argument("--symbols", nargs="*")
    risk.add_argument("--limit", type=int, default=24)
    risk.set_defaults(func=_cmd_risk)

    monitor_events = subparsers.add_parser("monitor-events", help="Inspect external monitor events stored in SQLite")
    monitor_events.add_argument("--lookback-hours", type=int)
    monitor_events.add_argument("--limit", type=int)
    monitor_events.add_argument("--add-sample", help="Insert a sample event with this ID for bridge testing")
    monitor_events.add_argument("--sync-sheet", action="store_true", help="Import monitor events from Google Sheet")
    monitor_events.add_argument("--sheet-url", help="Override GOOGLE_SHEET_MONITOR_URL for this import")
    monitor_events.add_argument("--symbol")
    monitor_events.add_argument("--title")
    monitor_events.add_argument("--severity", default="medium")
    monitor_events.add_argument("--event-time", default=datetime.utcnow().isoformat(timespec="seconds"))
    monitor_events.set_defaults(func=_cmd_monitor_events)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
