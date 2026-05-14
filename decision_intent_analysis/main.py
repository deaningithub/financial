from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import re
import sqlite3

from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DB_PATH = Path(os.getenv("FINANCIAL_DB_PATH", ROOT.parent / "data" / "financial_data.db"))
OUTPUT_DIR = Path(os.getenv("INTENT_OUTPUT_DIR", ROOT / "outputs"))


@dataclass(frozen=True)
class IntentActor:
    key: str
    name: str
    actor_type: str
    keywords: tuple[str, ...]
    likely_objectives: tuple[str, ...]
    watch_markers: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceItem:
    day: str
    source_type: str
    title: str
    source: str
    link: str | None
    score: float


@dataclass(frozen=True)
class IntentHypothesis:
    actor: IntentActor
    evidence: tuple[EvidenceItem, ...]
    inferred_objective: str
    confidence: float
    leading_indicators: tuple[str, ...]
    counter_evidence_needed: tuple[str, ...]


ACTORS: tuple[IntentActor, ...] = (
    IntentActor(
        key="white_house",
        name="White House",
        actor_type="policy",
        keywords=(
            "white house",
            "tariff",
            "export control",
            "industrial policy",
            "ai policy",
            "energy policy",
            "semiconductor",
            "china",
            "data center",
            "defense",
        ),
        likely_objectives=(
            "Preserve U.S. technology leadership while limiting strategic leakage to China.",
            "Shift critical manufacturing and infrastructure investment toward U.S.-aligned supply chains.",
            "Use tariffs, export controls, subsidies, and energy policy to steer corporate capital allocation.",
        ),
        watch_markers=(
            "new tariff or exemption language",
            "export-control entity list changes",
            "CHIPS/energy permitting announcements",
            "AI data-center power policy",
            "public pressure on large technology companies",
        ),
    ),
    IntentActor(
        key="pentagon",
        name="Pentagon / Department of Defense",
        actor_type="policy",
        keywords=(
            "pentagon",
            "department of defense",
            "missile defense",
            "defense procurement",
            "space defense",
            "ai strategy",
            "semiconductor supply chain",
            "drone",
        ),
        likely_objectives=(
            "Secure resilient compute, satellite, and defense supply chains.",
            "Accelerate procurement toward AI-enabled defense, missile defense, space, and autonomous systems.",
            "Reduce dependence on fragile or adversarial manufacturing chokepoints.",
        ),
        watch_markers=(
            "contract awards",
            "budget reprogramming",
            "procurement acceleration",
            "defense industrial base language",
            "strategic supplier announcements",
        ),
    ),
    IntentActor(
        key="apple",
        name="Apple",
        actor_type="technology_company",
        keywords=(
            "apple",
            "iphone",
            "aapl",
            "foxconn",
            "hon hai",
            "pegatron",
            "largan",
            "tsmc",
            "supply chain",
            "build plan",
        ),
        likely_objectives=(
            "Protect iPhone margin and supply continuity while shifting parts of assembly and sourcing geography.",
            "Lock in advanced-node chip access at TSMC while managing demand-cycle inventory risk.",
            "Use AI features and hardware refresh timing to defend replacement demand.",
        ),
        watch_markers=(
            "iPhone build-plan revisions",
            "supplier guidance from Hon Hai, Pegatron, Largan, and TSMC",
            "inventory correction language",
            "India/China assembly mix changes",
            "A-series or M-series chip order reports",
        ),
    ),
    IntentActor(
        key="nvidia",
        name="Nvidia",
        actor_type="technology_company",
        keywords=(
            "nvidia",
            "nvda",
            "gpu",
            "blackwell",
            "ai accelerator",
            "tsmc",
            "cowos",
            "hbm",
            "export control",
            "data center",
        ),
        likely_objectives=(
            "Preserve AI accelerator pricing power by controlling supply, platform lock-in, and software ecosystem gravity.",
            "Secure TSMC advanced packaging and HBM supply before competitors can close the gap.",
            "Navigate export controls by segmenting products and customers without losing long-term market access.",
        ),
        watch_markers=(
            "TSMC/CoWoS capacity language",
            "HBM supply agreements",
            "China-compliant chip announcements",
            "hyperscaler capex guidance",
            "gross margin commentary",
        ),
    ),
    IntentActor(
        key="hyperscalers",
        name="U.S. hyperscalers",
        actor_type="technology_company",
        keywords=(
            "microsoft",
            "google",
            "alphabet",
            "amazon",
            "aws",
            "meta",
            "oracle",
            "cloud capex",
            "data center",
            "taiwan investment",
            "ai capex",
            "tpu",
        ),
        likely_objectives=(
            "Secure AI compute capacity and energy access before demand visibility is fully proven.",
            "Use overseas data-center and supplier investment to diversify deployment bottlenecks.",
            "Reduce dependency on any single accelerator vendor through ASICs, TPUs, and custom silicon.",
        ),
        watch_markers=(
            "cloud capex revisions",
            "Taiwan data-center or cloud-region announcements",
            "custom silicon orders",
            "power purchase agreements",
            "server orders at Quanta, Wiwynn, Delta, and TSMC",
        ),
    ),
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _tokenize(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9&.-]{2,}", value)}


def _score_text(text: str, actor: IntentActor) -> float:
    lower = text.lower()
    score = 0.0
    for keyword in actor.keywords:
        if keyword.lower() in lower:
            score += 3.0 if " " in keyword else 1.5
    tokens = _tokenize(lower)
    objective_tokens = set()
    for objective in actor.likely_objectives:
        objective_tokens |= _tokenize(objective)
    score += len(tokens & objective_tokens) * 0.2
    return score


def _days_since(day: str, end_day: str) -> int:
    try:
        left = datetime.strptime(day, "%Y-%m-%d").date()
        right = datetime.strptime(end_day, "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(0, (right - left).days)


def _load_evidence(actor: IntentActor, end_day: str, lookback_days: int, max_items: int = 12) -> list[EvidenceItem]:
    cutoff = (datetime.strptime(end_day, "%Y-%m-%d").date() - timedelta(days=lookback_days)).isoformat()
    evidence: list[EvidenceItem] = []
    with _connect() as connection:
        news_rows = connection.execute(
            """
            SELECT day, query, title, source, link
            FROM news_items
            WHERE day >= ? AND day <= ?
            ORDER BY day DESC
            """,
            (cutoff, end_day),
        ).fetchall()
        report_rows = connection.execute(
            """
            SELECT day, report_markdown, ai_report
            FROM daily_reports
            WHERE day >= ? AND day <= ?
            ORDER BY day DESC
            """,
            (cutoff, end_day),
        ).fetchall()
        monitor_rows = connection.execute(
            """
            SELECT event_time, title, source, symbol, event_type, payload_json
            FROM monitor_events
            ORDER BY event_time DESC
            LIMIT 300
            """
        ).fetchall()

    for row in news_rows:
        text = f"{row['query']} {row['title']} {row['source']}"
        score = _score_text(text, actor)
        if score <= 0:
            continue
        score *= 1.0 / (1.0 + _days_since(row["day"], end_day) * 0.12)
        evidence.append(EvidenceItem(row["day"], "news", row["title"], row["source"], row["link"], score))

    for row in report_rows:
        text = (row["ai_report"] or row["report_markdown"] or "")[:6000]
        score = _score_text(text, actor)
        if score <= 0:
            continue
        score *= 0.6 / (1.0 + _days_since(row["day"], end_day) * 0.12)
        evidence.append(EvidenceItem(row["day"], "daily_report", f"Daily report context for {actor.name}", "daily_reports", None, score))

    cutoff_date = datetime.strptime(cutoff, "%Y-%m-%d").date()
    for row in monitor_rows:
        event_time = str(row["event_time"] or "")
        event_day = event_time[:10]
        try:
            if datetime.strptime(event_day, "%Y-%m-%d").date() < cutoff_date:
                continue
        except ValueError:
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        text = f"{row['title']} {row['source']} {row['symbol']} {row['event_type']} {payload}"
        score = _score_text(text, actor)
        if score <= 0:
            continue
        evidence.append(EvidenceItem(event_day, "monitor_event", row["title"], row["source"], None, score * 0.8))

    return sorted(evidence, key=lambda item: (item.score, item.day), reverse=True)[:max_items]


def _confidence(evidence: list[EvidenceItem]) -> float:
    if not evidence:
        return 0.0
    source_types = {item.source_type for item in evidence}
    raw = sum(item.score for item in evidence[:8])
    source_bonus = min(0.2, len(source_types) * 0.06)
    return min(0.9, 0.18 + raw / 40.0 + source_bonus)


def _pick_objective(actor: IntentActor, evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return actor.likely_objectives[0]
    evidence_text = " ".join(item.title.lower() for item in evidence[:6])
    best = actor.likely_objectives[0]
    best_score = -1
    for objective in actor.likely_objectives:
        score = len(_tokenize(objective.lower()) & _tokenize(evidence_text))
        if score > best_score:
            best = objective
            best_score = score
    return best


def build_intent_hypotheses(day: str, lookback_days: int, actor_keys: set[str] | None = None) -> list[IntentHypothesis]:
    selected = [actor for actor in ACTORS if not actor_keys or actor.key in actor_keys]
    hypotheses: list[IntentHypothesis] = []
    for actor in selected:
        evidence = _load_evidence(actor, day, lookback_days)
        hypotheses.append(
            IntentHypothesis(
                actor=actor,
                evidence=tuple(evidence),
                inferred_objective=_pick_objective(actor, evidence),
                confidence=_confidence(evidence),
                leading_indicators=actor.watch_markers[:4],
                counter_evidence_needed=(
                    "Direct management or official denial that contradicts the inferred objective.",
                    "Capital allocation, order, or policy data moving opposite to the hypothesis.",
                    "No follow-through in market-sensitive suppliers, customers, or policy channels over the next 2-4 weeks.",
                ),
            )
        )
    return sorted(hypotheses, key=lambda item: item.confidence, reverse=True)


def _confidence_label(value: float) -> str:
    if value >= 0.7:
        return "high"
    if value >= 0.45:
        return "medium"
    if value > 0:
        return "low"
    return "insufficient"


def render_report(day: str, hypotheses: list[IntentHypothesis], lookback_days: int) -> str:
    lines = [
        f"# Decision Intent Analysis - {day}",
        "",
        "This standalone project reads the existing daily financial database and turns scattered policy, company, market, and monitor signals into testable intent hypotheses.",
        "",
        "Important guardrail: this report does not claim to know private motives. It ranks plausible objectives from observable evidence and lists what would confirm or falsify them.",
        "",
        f"Lookback window: {lookback_days} days",
        "",
        "## Executive Hypotheses",
        "",
    ]
    for item in hypotheses:
        lines.append(
            f"- **{item.actor.name}**: {_confidence_label(item.confidence)} confidence "
            f"({item.confidence:.2f}) that the current signal points toward: {item.inferred_objective}"
        )

    for item in hypotheses:
        lines.extend([
            "",
            f"## {item.actor.name}",
            "",
            f"- Actor type: `{item.actor.actor_type}`",
            f"- Confidence: `{_confidence_label(item.confidence)}` ({item.confidence:.2f})",
            f"- Primary hypothesis: {item.inferred_objective}",
            "",
            "### Evidence",
        ])
        if item.evidence:
            for evidence in item.evidence[:8]:
                link = f" [{evidence.link}]({evidence.link})" if evidence.link else ""
                lines.append(
                    f"- {evidence.day} [{evidence.source_type}] {evidence.title} "
                    f"({evidence.source}, score={evidence.score:.1f}){link}"
                )
        else:
            lines.append("- No strong matching evidence in the current lookback window.")

        lines.extend(["", "### Watch Next"])
        for marker in item.leading_indicators:
            lines.append(f"- {marker}")
        lines.extend(["", "### What Would Falsify This"])
        for counter in item.counter_evidence_needed:
            lines.append(f"- {counter}")

    lines.extend(["", "_This is scenario analysis, not financial advice._", ""])
    return "\n".join(lines)


def create_ai_overlay(report_markdown: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    prompt = f"""You are an evidence-first geopolitical and technology strategy analyst.

Read the following deterministic intent-analysis report. Write a concise overlay that:
- sharpens the top 3 intent hypotheses,
- separates evidence from inference,
- names the biggest missing evidence,
- avoids conspiracy claims and avoids claiming private knowledge.

Report:
{report_markdown[:14000]}
"""
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "Write in English. Be skeptical, precise, and evidence-bound."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.output_text


def run_analysis(day: str, lookback_days: int, actor_keys: set[str] | None, use_ai: bool) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    hypotheses = build_intent_hypotheses(day=day, lookback_days=lookback_days, actor_keys=actor_keys)
    report = render_report(day=day, hypotheses=hypotheses, lookback_days=lookback_days)
    if use_ai:
        overlay = create_ai_overlay(report)
        if overlay:
            report = report.replace("## Executive Hypotheses", f"## AI Analyst Overlay\n\n{overlay}\n\n## Executive Hypotheses")
    path = OUTPUT_DIR / f"intent_report_{day}.md"
    path.write_text(report, encoding="utf-8")
    return path


def _cmd_actors(_: argparse.Namespace) -> None:
    for actor in ACTORS:
        print(f"{actor.key}: {actor.name} [{actor.actor_type}]")


def _cmd_run(args: argparse.Namespace) -> None:
    day = args.date or datetime.now().date().isoformat()
    actor_keys = set(args.actors or []) if args.actors else None
    path = run_analysis(day=day, lookback_days=args.lookback_days, actor_keys=actor_keys, use_ai=not args.no_ai)
    print(f"Decision intent analysis report created: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decision intent analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    actors = subparsers.add_parser("actors", help="List configured actors")
    actors.set_defaults(func=_cmd_actors)

    run = subparsers.add_parser("run", help="Create a decision intent analysis report")
    run.add_argument("--date")
    run.add_argument("--lookback-days", type=int, default=14)
    run.add_argument("--actors", nargs="*", choices=[actor.key for actor in ACTORS])
    run.add_argument("--no-ai", action="store_true", help="Skip optional OpenAI overlay")
    run.set_defaults(func=_cmd_run)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
