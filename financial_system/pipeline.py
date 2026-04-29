from __future__ import annotations

from financial_system.anomaly import build_anomaly_queries, rank_biggest_movers
from financial_system.config import (
    DATA_DIR,
    OUTPUT_DIR,
    ensure_directories,
    load_correlation_pairs,
    load_settings,
    load_trend_monitors,
    read_symbols,
)
from financial_system.correlation import compute_cross_market_correlations
from financial_system.database import (
    init_db,
    save_market_snapshots as save_market_snapshots_db,
    save_news as save_news_db,
    save_notes,
    save_keyword_scores,
    load_historical_keyword_scores,
    load_related_reports,
    save_daily_report,
    save_risk_metrics,
)
from financial_system.dates import today_string
from financial_system.dynamic_weights import build_dynamic_condition_queries
from financial_system.keywords import (
    build_keyword_queries,
    build_policy_queries,
    blend_keywords,
    rank_keywords,
)
from financial_system.llm import create_ai_report
from financial_system.market import fetch_market_snapshots, save_market_snapshots
from financial_system.news import collect_news, save_news
from financial_system.notes import read_notes
from financial_system.report import render_report, save_report
from financial_system.risk_analyzer import calculate_risk_metrics
from financial_system.trend_monitor import (
    build_long_term_trend_queries,
    evaluate_long_term_trends,
)


def _score_terms(terms: list[str], score: float) -> dict[str, float]:
    return {term: score for term in terms if term}


def _build_report_keyword_scores(
    current_scores: list[tuple[str, float]],
    primary_keywords: list[str],
    secondary_keywords: list[str],
    long_term_trend_queries: list[str],
    policy_queries: list[str],
    movers: list,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for term, score in current_scores:
        scores[term] = scores.get(term, 0.0) + float(score)
    for term, score in _score_terms(primary_keywords, 2.0).items():
        scores[term] = scores.get(term, 0.0) + score
    for term, score in _score_terms(secondary_keywords, 1.25).items():
        scores[term] = scores.get(term, 0.0) + score
    for query, score in _score_terms(long_term_trend_queries, 1.5).items():
        scores[query] = scores.get(query, 0.0) + score
    for query, score in _score_terms(policy_queries, 1.2).items():
        scores[query] = scores.get(query, 0.0) + score
    for mover in movers:
        move_score = abs(mover.daily_change_pct or 0) or 1.0
        scores[mover.symbol] = scores.get(mover.symbol, 0.0) + move_score
        scores[mover.name.lower()] = scores.get(mover.name.lower(), 0.0) + move_score
    return scores


def run_daily_pipeline(day: str | None = None, use_ai: bool = True) -> dict[str, str]:
    ensure_directories()
    settings = load_settings()
    init_db()
    day = day or today_string(settings.timezone)

    notes = read_notes(DATA_DIR / "manual_notes", day)
    symbols = read_symbols()
    snapshots = fetch_market_snapshots(symbols)
    movers = rank_biggest_movers(snapshots)
    risk_metrics = calculate_risk_metrics(snapshots, day=day)

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
    trend_config = load_trend_monitors()
    long_term_alerts = evaluate_long_term_trends(trend_config, snapshots)
    long_term_trend_queries = build_long_term_trend_queries(
        long_term_alerts,
        max_queries=settings.long_term_trend_query_limit,
    )
    policy_queries = build_policy_queries(
        snapshots,
        policy_limit=settings.policy_query_limit,
        company_limit=settings.policy_company_query_limit,
    )
    dynamic_queries = build_dynamic_condition_queries(snapshots, max_queries=8)
    correlations = compute_cross_market_correlations(
        load_correlation_pairs(),
        lookback_days=settings.correlation_lookback_days,
        min_abs_correlation=settings.correlation_min_abs,
    )
    anomaly_queries = build_anomaly_queries(movers)
    queries = anomaly_queries + dynamic_queries + keyword_queries + secondary_queries + policy_queries + long_term_trend_queries
    report_keyword_scores = _build_report_keyword_scores(
        current_scores=current_scores,
        primary_keywords=primary_keywords,
        secondary_keywords=secondary_keywords,
        long_term_trend_queries=long_term_trend_queries,
        policy_queries=policy_queries + dynamic_queries,
        movers=movers,
    )
    related_reports = load_related_reports(
        report_keyword_scores,
        min_reports=settings.report_context_min,
        lookback_days=settings.report_context_lookback_days,
        exclude_days={day},
    )
    news_items = collect_news(
        queries,
        limit_per_query=4,
        max_age_days=14,
        locales=settings.news_locales,
        source_limit=settings.source_news_limit,
    ) if queries else []

    market_path = DATA_DIR / "market_snapshots" / f"{day}.json"
    news_path = DATA_DIR / "news" / f"{day}.json"
    report_path = OUTPUT_DIR / f"daily_report_{day}.md"

    save_market_snapshots(market_path, snapshots)
    save_news(news_path, news_items)
    save_market_snapshots_db(day, snapshots)
    save_news_db(day, news_items)
    save_notes(day, notes)
    save_risk_metrics(day, risk_metrics)

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
            related_reports=related_reports,
            long_term_alerts=long_term_alerts,
            correlations=correlations,
            risk_metrics=risk_metrics,
        )

    report = render_report(
        day=day,
        notes=notes,
        snapshots=snapshots,
        movers=movers,
        news_items=news_items,
        ai_report=ai_report,
        risk_metrics=risk_metrics,
    )
    save_report(report_path, report)
    save_daily_report(
        day=day,
        report_markdown=report,
        ai_report=ai_report,
        keyword_scores=report_keyword_scores,
    )

    return {
        "report": str(report_path),
        "market_snapshot": str(market_path),
        "news": str(news_path),
    }
