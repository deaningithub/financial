from __future__ import annotations

import argparse

from taiwan_stock_valuation import (
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


def _fmt_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _cmd_init(args: argparse.Namespace) -> None:
    path = init_taiwan_stock_valuation_db(seed_stocks=not args.no_seed)
    print(f"Initialized Taiwan stock valuation database: {path}")


def _cmd_list(_: argparse.Namespace) -> None:
    init_taiwan_stock_valuation_db(seed_stocks=False)
    for stock in list_taiwan_stocks():
        industry = " / ".join(part for part in [stock.industry, stock.sub_industry] if part)
        print(f"{stock.stock_id} {stock.stock_name} [{stock.market or 'unknown'}] {industry or 'uncategorized'}")


def _cmd_add(args: argparse.Namespace) -> None:
    add_taiwan_stock(
        stock_id=args.stock_id,
        stock_name=args.name,
        market=args.market,
        industry=args.industry,
        sub_industry=args.sub_industry,
        note=args.note,
    )
    print(f"Upserted Taiwan stock: {args.stock_id} {args.name}")


def _cmd_create_task(args: argparse.Namespace) -> None:
    task_id = create_ai_research_task(args.stock_id, args.task_type, args.priority)
    print(f"Created AI research task #{task_id}")


def _cmd_add_financial(args: argparse.Namespace) -> None:
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


def _cmd_add_price(args: argparse.Namespace) -> None:
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


def _cmd_import_financial_csv(args: argparse.Namespace) -> None:
    print(f"Imported financial statement rows: {import_financial_statements_csv(args.path)}")


def _cmd_import_price_csv(args: argparse.Namespace) -> None:
    print(f"Imported market price rows: {import_market_prices_csv(args.path)}")


def _cmd_calc_valuation(args: argparse.Namespace) -> None:
    result = calculate_valuation_metrics(args.stock_id, args.calc_date)
    print(
        f"{result.stock_id} valuation on {result.calc_date}: "
        f"method={result.valuation_method}, price={_fmt_number(result.close_price)}, "
        f"fair_value={_fmt_number(result.fair_value_bear)}/"
        f"{_fmt_number(result.fair_value_base)}/{_fmt_number(result.fair_value_bull)}, "
        f"margin_of_safety={_fmt_number(result.margin_of_safety)}%"
    )


def _cmd_run_research(args: argparse.Namespace) -> None:
    report_path = run_taiwan_stock_research(
        stock_id=args.stock_id,
        task_id=args.task_id,
        report_date=args.report_date,
        use_ai=not args.no_ai,
    )
    print(f"Taiwan stock research report created: {report_path}")


def _cmd_show_report(args: argparse.Namespace) -> None:
    report = get_final_report(args.stock_id, report_date=args.report_date)
    if report is None:
        print("No final report found.")
        return
    if args.summary:
        print(f"{report['stock_id']} {report['report_date']} rating={report['rating']} score={_fmt_number(report['final_score'])}")
        print(report["one_line_summary"] or "")
        return
    print(report["report_markdown"] or "")


def _cmd_show_rounds(args: argparse.Namespace) -> None:
    rounds = list_ai_research_rounds(args.stock_id, task_id=args.task_id)
    if not rounds:
        print("No AI research rounds found.")
        return
    for item in rounds:
        print(f"task={item['task_id']} round={item['round_number']} role={item['agent_role']}")
        print(item["summary"] or "")
        if args.details:
            print("Key facts:")
            print(item["key_facts"] or "")
            print("Assumptions:")
            print(item["assumptions"] or "")
            print("Risks:")
            print(item["risks"] or "")
        print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detached Taiwan stock valuation research workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--no-seed", action="store_true")
    init.set_defaults(func=_cmd_init)

    list_cmd = subparsers.add_parser("list")
    list_cmd.set_defaults(func=_cmd_list)

    add = subparsers.add_parser("add")
    add.add_argument("--stock-id", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--market", default="TWSE")
    add.add_argument("--industry")
    add.add_argument("--sub-industry")
    add.add_argument("--note")
    add.set_defaults(func=_cmd_add)

    create_task = subparsers.add_parser("create-task")
    create_task.add_argument("--stock-id", required=True)
    create_task.add_argument("--task-type", default="full_research")
    create_task.add_argument("--priority", type=int, default=5)
    create_task.set_defaults(func=_cmd_create_task)

    financial = subparsers.add_parser("add-financial")
    financial.add_argument("--stock-id", required=True)
    financial.add_argument("--year", type=int, required=True)
    financial.add_argument("--quarter", type=int, required=True, choices=[1, 2, 3, 4])
    for name in [
        "revenue",
        "gross-profit",
        "operating-income",
        "net-income",
        "eps",
        "total-assets",
        "total-liabilities",
        "equity",
        "cash-and-equivalents",
        "total-debt",
        "operating-cash-flow",
        "investing-cash-flow",
        "financing-cash-flow",
        "free-cash-flow",
        "gross-margin",
        "operating-margin",
        "net-margin",
        "roe",
        "roa",
    ]:
        financial.add_argument(f"--{name}", type=float)
    financial.add_argument("--source", default="manual")
    financial.set_defaults(func=_cmd_add_financial)

    price = subparsers.add_parser("add-price")
    price.add_argument("--stock-id", required=True)
    price.add_argument("--trade-date", required=True)
    for name in ["open-price", "high-price", "low-price", "close-price", "volume", "market-cap"]:
        price.add_argument(f"--{name}", type=float)
    price.add_argument("--source", default="manual")
    price.set_defaults(func=_cmd_add_price)

    import_financial = subparsers.add_parser("import-financial-csv")
    import_financial.add_argument("--path", required=True)
    import_financial.set_defaults(func=_cmd_import_financial_csv)

    import_price = subparsers.add_parser("import-price-csv")
    import_price.add_argument("--path", required=True)
    import_price.set_defaults(func=_cmd_import_price_csv)

    valuation = subparsers.add_parser("calc-valuation")
    valuation.add_argument("--stock-id", required=True)
    valuation.add_argument("--calc-date")
    valuation.set_defaults(func=_cmd_calc_valuation)

    research = subparsers.add_parser("run-research")
    research.add_argument("--stock-id", required=True)
    research.add_argument("--task-id", type=int)
    research.add_argument("--report-date")
    research.add_argument("--no-ai", action="store_true")
    research.set_defaults(func=_cmd_run_research)

    show_report = subparsers.add_parser("show-report")
    show_report.add_argument("--stock-id", required=True)
    show_report.add_argument("--report-date")
    show_report.add_argument("--summary", action="store_true")
    show_report.set_defaults(func=_cmd_show_report)

    show_rounds = subparsers.add_parser("show-rounds")
    show_rounds.add_argument("--stock-id", required=True)
    show_rounds.add_argument("--task-id", type=int)
    show_rounds.add_argument("--details", action="store_true")
    show_rounds.set_defaults(func=_cmd_show_rounds)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
