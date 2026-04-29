from __future__ import annotations

from financial_system.anomaly import build_anomaly_queries, rank_biggest_movers
from financial_system.config import (
    DATA_DIR,
    OUTPUT_DIR,
    ensure_directories,
    load_settings,
    load_trend_keywords,
    read_symbols,
)
from financial_system.database import (
    init_db,
    save_market_snapshots as save_market_snapshots_db,
    save_news as save_news_db,
    save_notes,
    save_keyword_scores,
    load_historical_keyword_scores,
)
from financial_system.dates import today_string
from financial_system.keywords import (
    build_keyword_queries,
    build_policy_queries,
    build_trend_queries,
    blend_keywords,
    rank_keywords,
)
from financial_system.llm import create_ai_report
from financial_system.market import fetch_market_snapshots, save_market_snapshots
from financial_system.news import collect_news, save_news
from financial_system.notes import read_notes
from financial_system.report import render_report, save_report


def run_daily_pipeline(day: str | None = None, use_ai: bool = True) -> dict[str, str]:
    ensure_directories()
    settings = load_settings()
    init_db()
    day = day or today_string(settings.timezone)

    notes = read_notes(DATA_DIR / "manual_notes", day)
    symbols = read_symbols()
    snapshots = fetch_market_snapshots(symbols)
    movers = rank_biggest_movers(snapshots)

    current_scores = rank_keywords(notes, limit=settings.keyword_limit)
    historical_scores = load_historical_keyword_scores(
        max_days=settings.keyword_retention_days,
        decay=settings.keyword_decay_factor,
        min_score=settings.keyword_min_score,
        exclude_days={day},
    )
    primary_keywords, secondary_keywords = blend_keywords(
        current_scores,
        historical_scores,
        primary_limit=settings.keyword_limit,
        secondary_limit=settings.keyword_secondary_limit,
    )
    save_keyword_scores(day, current_scores)

    keyword_queries = build_keyword_queries(primary_keywords, max_queries=settings.keyword_query_limit)
    secondary_queries = build_keyword_queries(secondary_keywords, max_queries=settings.keyword_secondary_limit)
    trend_config = load_trend_keywords()
    trend_queries = build_trend_queries(trend_config, max_queries=settings.trend_query_limit)
    policy_queries = build_policy_queries(
        snapshots,
        policy_limit=settings.policy_query_limit,
        company_limit=settings.policy_company_query_limit,
    )
    anomaly_queries = build_anomaly_queries(movers)
    queries = anomaly_queries + trend_queries + keyword_queries + secondary_queries + policy_queries
    news_items = collect_news(
        queries,
        limit_per_query=4,
        max_age_days=14,
        locales=settings.news_locales,
    ) if queries else []

    market_path = DATA_DIR / "market_snapshots" / f"{day}.json"
    news_path = DATA_DIR / "news" / f"{day}.json"
    report_path = OUTPUT_DIR / f"daily_report_{day}.md"

    save_market_snapshots(market_path, snapshots)
    save_news(news_path, news_items)
    save_market_snapshots_db(day, snapshots)
    save_news_db(day, news_items)
    save_notes(day, notes)

    ai_report = None
    if use_ai and settings.openai_api_key:
        ai_report = create_ai_report(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            day=day,
            notes=notes,
            snapshots=snapshots,
            movers=movers,
            news_items=news_items,
        )

    report = render_report(
        day=day,
        notes=notes,
        snapshots=snapshots,
        movers=movers,
        news_items=news_items,
        ai_report=ai_report,
    )
    save_report(report_path, report)

    return {
        "report": str(report_path),
        "market_snapshot": str(market_path),
        "news": str(news_path),
    }
