from __future__ import annotations

from openai import OpenAI

from financial_system.market import MarketSnapshot
from financial_system.monitor_bridge import MonitorEvent, format_monitor_events
from financial_system.news import NewsItem
from financial_system.trend_monitor import TrendAlert, format_trend_alerts
from financial_system.correlation import CorrelationResult, format_correlations
from financial_system.risk_analyzer import RiskMetrics, format_risk_metrics


SYSTEM_PROMPT = """You are a financial intelligence analyst.

Create a grounded daily market brief from the provided market data, user notes, news links, related historical reports, external monitor events, risk metrics, cross-market correlations, and long-term trend monitor status.

Rules:
- Write the entire report in English.
- Do not invent causes. If a cause is only suggested by headlines, label it as a likely driver.
- Separate facts, interpretation, and risk assessment.
- Use related historical reports as context, but do not treat old information as today's fact.
- Use the immediately previous report as continuity context. Repeat only still-important points; skip background that was already explained and is no longer central.
- If a previous same-day run is provided, treat it as the strongest continuity context.
- Clearly identify whether today's market action continues or reverses themes from related historical reports.
- Filter repeated news and stale context. Re-state an already-covered item only when there is a new fact, new price reaction, or changed risk implication.
- When information overlaps with the previous report, summarize it in one concise sentence instead of repeating the whole explanation.
- Make the daily report primarily about short-term international political and economic conditions.
- Treat long-term themes as monitored background. Discuss them in detail only when a monitor alert is provided.
- Include both upside and downside risks.
- Keep the report concise, practical, and useful for a human investor.
- This is not financial advice.
"""


def _market_lines(snapshots: list[MarketSnapshot]) -> str:
    lines = []
    for item in snapshots:
        lines.append(
            f"{item.name} ({item.symbol}, region={item.region}, type={item.asset_type}): price={item.last_price}, "
            f"daily_change_pct={item.daily_change_pct}, "
            f"5d_change_pct={item.five_day_change_pct}, "
            f"1m_change_pct={item.one_month_change_pct}, status={item.status}"
        )
    return "\n".join(lines)


def _news_lines(news_items: list[NewsItem]) -> str:
    return "\n".join(
        f"- [{item.query}] {item.title} ({item.source}) {item.link}"
        for item in news_items
    )


def _historical_report_lines(related_reports: list[dict]) -> str:
    if not related_reports:
        return "No related historical reports available."

    blocks = []
    for report in related_reports:
        ai_report = report.get("ai_report") or report.get("report_markdown") or ""
        excerpt = ai_report.strip().replace("\r\n", "\n")[:2200]
        matched_terms = ", ".join(report.get("matched_terms") or [])
        context_role = report.get("context_role") or "related_report"
        blocks.append(
            f"Date: {report.get('day')}\n"
            f"Context role: {context_role}\n"
            f"Relevance score: {report.get('relevance', 0):.2f}\n"
            f"Matched keywords: {matched_terms or 'fallback recent report'}\n"
            f"Report excerpt:\n{excerpt}"
        )
    return "\n\n---\n\n".join(blocks)


def create_ai_report(
    api_key: str,
    model: str,
    day: str,
    notes: str,
    snapshots: list[MarketSnapshot],
    movers: list[MarketSnapshot],
    news_items: list[NewsItem],
    related_reports: list[dict] | None = None,
    long_term_alerts: list[TrendAlert] | None = None,
    correlations: list[CorrelationResult] | None = None,
    risk_metrics: list[RiskMetrics] | None = None,
    monitor_events: list[MonitorEvent] | None = None,
    target_words: int = 1500,
) -> str:
    client = OpenAI(api_key=api_key)
    mover_names = ", ".join(
        f"{mover.name} {mover.daily_change_pct:.2f}%"
        for mover in movers
        if mover.daily_change_pct is not None
    )
    user_prompt = f"""Date: {day}

User notes:
{notes or "No manual notes provided."}

Market data:
{_market_lines(snapshots)}

Biggest movers:
{mover_names or "No movers detected."}

Collected news:
{_news_lines(news_items) or "No news collected."}

Previous and related historical reports:
{_historical_report_lines(related_reports or [])}

Long-term trend monitor status:
{format_trend_alerts(long_term_alerts or [])}

Risk dashboard:
{format_risk_metrics(risk_metrics or [])}

External monitor events from SQLite bridge:
{format_monitor_events(monitor_events or [])}

Cross-market correlation analysis:
{format_correlations(correlations or [])}

Write in English.

Target length: about {target_words} English words. Prefer concise paragraphs and avoid restating non-essential background.

Use the previous and related historical reports first to establish context:
- Treat any report marked "previous report" as the immediate narrative continuation point.
- Which themes are continuing?
- Which themes are reversing?
- Which old risks still matter today?
- Re-mention important prior points only when they are still material today. If an older point is no longer central, skip it.
- Reference historical reports when the system provides them. If the previous report is unavailable, state that continuity context is unavailable.

The daily report should focus on short-term international political and economic conditions: rates, inflation, oil, currencies, geopolitics, policy changes, earnings, and cross-market risk appetite.
Use the cross-market correlation analysis to identify synchronized risk-on/risk-off behavior or unusual divergence across the U.S., Taiwan, Europe, China/Hong Kong, Japan, India, commodities, yields, and currencies.
Use the risk dashboard to identify volatility, drawdown, beta, and concentration risks. Do not convert these risk metrics into trading instructions.
Use external monitor events only as alert context from another system. Do not assume the current project generated those alerts.

The following long-term framework should be treated as a monitoring layer, not the main report theme:
- AI chips: GPU, HBM, advanced packaging, data center capex, TSMC, and related supply chains.
- Satellite communications: low earth orbit satellites, satellite internet, ground equipment, and aerospace supply chains.
- Robotics and vehicle technology: humanoid robots, industrial automation, electric vehicles, autonomous driving, and automotive semiconductors.
- Space exploration and moon landing: moon programs, rocket launches, space infrastructure, aerospace materials, and components.

Only discuss a long-term trend in detail if the long-term trend monitor status shows an alert or if today's news has a direct market-moving catalyst. Otherwise, summarize it briefly as "no major threshold event today."

Write the daily financial summary and risk assessment with these concise sections:
1. Executive summary
2. Continuation from the previous report
3. Biggest moves and likely drivers
4. Taiwan market status
5. Short-term political and economic situation
6. Risk assessment and what to monitor next
"""
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.output_text
