from __future__ import annotations

import argparse
from datetime import datetime
from types import SimpleNamespace

from financial_system.config import DATA_DIR, ensure_directories, load_trend_monitors, read_symbols, write_symbols
from financial_system.dates import today_string
from financial_system.config import load_settings
from financial_system.database import (
    init_db,
    load_historical_keyword_scores,
    load_monitor_events,
    load_tracked_keyword_weights,
    load_tracked_keywords,
    save_monitor_event,
    save_monitor_events,
)
from financial_system.google_sheet_bridge import fetch_monitor_events_from_sheet
from financial_system.keywords import build_keyword_queries, build_policy_queries, blend_keywords, rank_keywords
from financial_system.monitor_bridge import MonitorEvent, format_monitor_events
from financial_system.notes import append_note
from financial_system.notes import read_notes
from financial_system.risk_analyzer import calculate_risk_metrics
from financial_system.market import fetch_market_snapshots
from financial_system.taiwan_stock_valuation import (
    add_taiwan_stock,
    calculate_valuation_metrics,
    create_ai_research_task,
    get_final_report,
    import_financial_statements_csv,
    import_market_prices_csv,
    init_taiwan_stock_valuation_db,
    list_ai_research_rounds,
    list_taiwan_stocks,
    run_taiwan_stock_research,
    upsert_financial_statement,
    upsert_market_price,
)


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
    tracked_keyword_weights = load_tracked_keyword_weights(
        limit=max(50, (args.limit or settings.keyword_limit) + (args.secondary_limit or settings.keyword_secondary_limit)),
        min_weight=settings.keyword_min_score,
    )
    for term, score in tracked_keyword_weights.items():
        historical_scores[term] = max(historical_scores.get(term, 0.0), score)
    primary_keywords, secondary_keywords = blend_keywords(
        ranked,
        historical_scores,
        primary_limit=args.limit or settings.keyword_limit,
        secondary_limit=args.secondary_limit or settings.keyword_secondary_limit,
    )
    primary_queries = build_keyword_queries(primary_keywords, max_queries=args.query_limit or settings.keyword_query_limit)
    secondary_queries = build_keyword_queries(secondary_keywords, max_queries=args.secondary_limit or settings.keyword_secondary_limit)
    tracked_queries = build_keyword_queries(
        list(tracked_keyword_weights.keys()),
        max_queries=max(50, (args.limit or settings.keyword_limit) + (args.secondary_limit or settings.keyword_secondary_limit)),
    )
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

    if tracked_queries:
        print("Tracked keyword search queries:")
        for query in tracked_queries:
            print(f"- {query}")

    tracked_keywords = load_tracked_keywords(limit=args.limit or settings.keyword_limit)
    if tracked_keywords:
        print("Tracked news keyword weights:")
        for item in tracked_keywords:
            print(
                f"- {item['term']}: weight={item['weight']:.2f}, "
                f"last_seen={item['last_seen_day']}, appearances={item['appearances']}"
            )

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


def _cmd_taiwan_stocks(args: argparse.Namespace) -> None:
    if args.action == "init":
        path = init_taiwan_stock_valuation_db(seed_stocks=not args.no_seed)
        print(f"Initialized Taiwan stock valuation database: {path}")
        if not args.no_seed:
            print("Seeded starter Taiwan stocks.")
        return

    if args.action == "list":
        init_taiwan_stock_valuation_db(seed_stocks=False)
        stocks = list_taiwan_stocks()
        if not stocks:
            print("No Taiwan stocks found. Run `python main.py taiwan-stocks init` first.")
            return
        for stock in stocks:
            industry = " / ".join(
                part for part in [stock.industry, stock.sub_industry] if part
            )
            suffix = f" - {stock.note}" if stock.note else ""
            print(
                f"{stock.stock_id} {stock.stock_name} "
                f"[{stock.market or 'unknown'}] {industry or 'uncategorized'} "
                f"status={stock.status}{suffix}"
            )
        return

    if args.action == "add":
        add_taiwan_stock(
            stock_id=args.stock_id,
            stock_name=args.name,
            market=args.market,
            industry=args.industry,
            sub_industry=args.sub_industry,
            note=args.note,
        )
        print(f"Upserted Taiwan stock: {args.stock_id} {args.name}")
        return

    if args.action == "create-task":
        task_id = create_ai_research_task(
            stock_id=args.stock_id,
            task_type=args.task_type,
            priority=args.priority,
        )
        print(
            f"Created AI research task #{task_id}: "
            f"stock_id={args.stock_id}, task_type={args.task_type}, priority={args.priority}"
        )
        return

    if args.action == "add-financial":
        upsert_financial_statement(
            stock_id=args.stock_id,
            year=args.year,
            quarter=args.quarter,
            values={
                "revenue": args.revenue,
                "gross_profit": args.gross_profit,
                "operating_income": args.operating_income,
                "net_income": args.net_income,
                "eps": args.eps,
                "total_assets": args.total_assets,
                "total_liabilities": args.total_liabilities,
                "equity": args.equity,
                "cash_and_equivalents": args.cash_and_equivalents,
                "total_debt": args.total_debt,
                "operating_cash_flow": args.operating_cash_flow,
                "investing_cash_flow": args.investing_cash_flow,
                "financing_cash_flow": args.financing_cash_flow,
                "free_cash_flow": args.free_cash_flow,
                "gross_margin": args.gross_margin,
                "operating_margin": args.operating_margin,
                "net_margin": args.net_margin,
                "roe": args.roe,
                "roa": args.roa,
                "source": args.source,
            },
        )
        print(f"Upserted financial statement: {args.stock_id} {args.year}Q{args.quarter}")
        return

    if args.action == "add-price":
        upsert_market_price(
            stock_id=args.stock_id,
            trade_date=args.trade_date,
            values={
                "open_price": args.open_price,
                "high_price": args.high_price,
                "low_price": args.low_price,
                "close_price": args.close_price,
                "volume": args.volume,
                "market_cap": args.market_cap,
                "source": args.source,
            },
        )
        print(f"Upserted market price: {args.stock_id} {args.trade_date}")
        return

    if args.action == "calc-valuation":
        result = calculate_valuation_metrics(
            stock_id=args.stock_id,
            calc_date=args.calc_date,
        )
        print(
            f"{result.stock_id} valuation on {result.calc_date}: "
            f"method={result.valuation_method}, "
            f"price={_fmt_number(result.close_price)}, "
            f"eps_ttm={_fmt_number(result.eps_ttm)}, "
            f"pe={_fmt_number(result.pe)}, "
            f"pb={_fmt_number(result.pb)}, "
            f"ps={_fmt_number(result.ps)}, "
            f"roe={_fmt_number(result.roe)}%, "
            f"fair_value={_fmt_number(result.fair_value_bear)}/"
            f"{_fmt_number(result.fair_value_base)}/"
            f"{_fmt_number(result.fair_value_bull)}, "
            f"margin_of_safety={_fmt_number(result.margin_of_safety)}%"
        )
        return

    if args.action == "run-research":
        report_path = run_taiwan_stock_research(
            stock_id=args.stock_id,
            task_id=args.task_id,
            report_date=args.report_date,
            use_ai=not args.no_ai,
        )
        print(f"Taiwan stock research report created: {report_path}")
        return

    if args.action == "import-financial-csv":
        imported = import_financial_statements_csv(args.path)
        print(f"Imported financial statement rows: {imported}")
        return

    if args.action == "import-price-csv":
        imported = import_market_prices_csv(args.path)
        print(f"Imported market price rows: {imported}")
        return

    if args.action == "show-report":
        report = get_final_report(args.stock_id, report_date=args.report_date)
        if report is None:
            print("No final report found.")
            return
        if args.summary:
            print(f"{report['stock_id']} {report['report_date']} rating={report['rating']} score={_fmt_number(report['final_score'])}")
            print(report["one_line_summary"] or "")
            return
        print(report["report_markdown"] or "")
        return

    if args.action == "show-rounds":
        rounds = list_ai_research_rounds(args.stock_id, task_id=args.task_id)
        if not rounds:
            print("No AI research rounds found.")
            return
        for item in rounds:
            print(
                f"task={item['task_id']} round={item['round_number']} "
                f"role={item['agent_role']} confidence={_fmt_number(item['confidence_score'])} "
                f"model={item['model_name']}"
            )
            print(item["summary"] or "")
            if args.details:
                print("Key facts:")
                print(item["key_facts"] or "")
                print("Assumptions:")
                print(item["assumptions"] or "")
                print("Risks:")
                print(item["risks"] or "")
            print("")
        return

    raise SystemExit(f"Unknown taiwan-stocks action: {args.action}")


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

    monitor_events = subparsers.add_parser("monitor-events", help="Inspect external monitor events from the configured state backend")
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

    taiwan_stocks = subparsers.add_parser("taiwan-stocks", help="Manage Taiwan stock valuation database")
    taiwan_subparsers = taiwan_stocks.add_subparsers(dest="action", required=True)

    taiwan_init = taiwan_subparsers.add_parser("init", help="Initialize Taiwan stock valuation SQLite schema")
    taiwan_init.add_argument("--no-seed", action="store_true", help="Create schema without inserting starter stocks")
    taiwan_init.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_list = taiwan_subparsers.add_parser("list", help="List Taiwan stocks in the valuation database")
    taiwan_list.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_add = taiwan_subparsers.add_parser("add", help="Add or update a Taiwan stock master record")
    taiwan_add.add_argument("--stock-id", required=True)
    taiwan_add.add_argument("--name", required=True)
    taiwan_add.add_argument("--market", default="TWSE")
    taiwan_add.add_argument("--industry")
    taiwan_add.add_argument("--sub-industry")
    taiwan_add.add_argument("--note")
    taiwan_add.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_task = taiwan_subparsers.add_parser("create-task", help="Create an AI research task for a Taiwan stock")
    taiwan_task.add_argument("--stock-id", required=True)
    taiwan_task.add_argument("--task-type", default="full_research")
    taiwan_task.add_argument("--priority", type=int, default=5)
    taiwan_task.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_financial = taiwan_subparsers.add_parser("add-financial", help="Add or update one quarterly financial statement")
    taiwan_financial.add_argument("--stock-id", required=True)
    taiwan_financial.add_argument("--year", type=int, required=True)
    taiwan_financial.add_argument("--quarter", type=int, required=True, choices=[1, 2, 3, 4])
    taiwan_financial.add_argument("--revenue", type=float)
    taiwan_financial.add_argument("--gross-profit", type=float)
    taiwan_financial.add_argument("--operating-income", type=float)
    taiwan_financial.add_argument("--net-income", type=float)
    taiwan_financial.add_argument("--eps", type=float)
    taiwan_financial.add_argument("--total-assets", type=float)
    taiwan_financial.add_argument("--total-liabilities", type=float)
    taiwan_financial.add_argument("--equity", type=float)
    taiwan_financial.add_argument("--cash-and-equivalents", type=float)
    taiwan_financial.add_argument("--total-debt", type=float)
    taiwan_financial.add_argument("--operating-cash-flow", type=float)
    taiwan_financial.add_argument("--investing-cash-flow", type=float)
    taiwan_financial.add_argument("--financing-cash-flow", type=float)
    taiwan_financial.add_argument("--free-cash-flow", type=float)
    taiwan_financial.add_argument("--gross-margin", type=float)
    taiwan_financial.add_argument("--operating-margin", type=float)
    taiwan_financial.add_argument("--net-margin", type=float)
    taiwan_financial.add_argument("--roe", type=float)
    taiwan_financial.add_argument("--roa", type=float)
    taiwan_financial.add_argument("--source", default="manual")
    taiwan_financial.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_price = taiwan_subparsers.add_parser("add-price", help="Add or update one daily market price")
    taiwan_price.add_argument("--stock-id", required=True)
    taiwan_price.add_argument("--trade-date", required=True)
    taiwan_price.add_argument("--open-price", type=float)
    taiwan_price.add_argument("--high-price", type=float)
    taiwan_price.add_argument("--low-price", type=float)
    taiwan_price.add_argument("--close-price", type=float)
    taiwan_price.add_argument("--volume", type=float)
    taiwan_price.add_argument("--market-cap", type=float)
    taiwan_price.add_argument("--source", default="manual")
    taiwan_price.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_valuation = taiwan_subparsers.add_parser("calc-valuation", help="Calculate and store valuation metrics")
    taiwan_valuation.add_argument("--stock-id", required=True)
    taiwan_valuation.add_argument("--calc-date")
    taiwan_valuation.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_research = taiwan_subparsers.add_parser("run-research", help="Run the 5-round Taiwan stock research workflow")
    taiwan_research.add_argument("--stock-id", required=True)
    taiwan_research.add_argument("--task-id", type=int)
    taiwan_research.add_argument("--report-date")
    taiwan_research.add_argument("--no-ai", action="store_true", help="Use deterministic local agents instead of OpenAI")
    taiwan_research.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_import_financial = taiwan_subparsers.add_parser("import-financial-csv", help="Import quarterly financial statements from CSV")
    taiwan_import_financial.add_argument("--path", required=True)
    taiwan_import_financial.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_import_price = taiwan_subparsers.add_parser("import-price-csv", help="Import daily market prices from CSV")
    taiwan_import_price.add_argument("--path", required=True)
    taiwan_import_price.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_show_report = taiwan_subparsers.add_parser("show-report", help="Read the latest or dated final report from SQLite")
    taiwan_show_report.add_argument("--stock-id", required=True)
    taiwan_show_report.add_argument("--report-date")
    taiwan_show_report.add_argument("--summary", action="store_true")
    taiwan_show_report.set_defaults(func=_cmd_taiwan_stocks)

    taiwan_show_rounds = taiwan_subparsers.add_parser("show-rounds", help="Read AI research round summaries from SQLite")
    taiwan_show_rounds.add_argument("--stock-id", required=True)
    taiwan_show_rounds.add_argument("--task-id", type=int)
    taiwan_show_rounds.add_argument("--details", action="store_true")
    taiwan_show_rounds.set_defaults(func=_cmd_taiwan_stocks)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
