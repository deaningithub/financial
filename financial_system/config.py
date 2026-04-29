from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
SYMBOLS_FILE = CONFIG_DIR / "symbols.json"
KEYWORD_WEIGHTS_FILE = CONFIG_DIR / "keyword_weights.json"
POLICY_KEYWORDS_FILE = CONFIG_DIR / "policy_keywords.json"
TREND_KEYWORDS_FILE = CONFIG_DIR / "trend_keywords.json"
TREND_MONITORS_FILE = CONFIG_DIR / "trend_monitors.json"
NEWS_SOURCES_FILE = CONFIG_DIR / "news_sources.json"
CORRELATION_PAIRS_FILE = CONFIG_DIR / "correlation_pairs.json"
DB_PATH = DATA_DIR / "financial_data.db"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    timezone: str
    keyword_limit: int
    keyword_query_limit: int
    keyword_secondary_limit: int
    keyword_retention_days: int
    keyword_decay_factor: float
    keyword_min_score: float
    policy_query_limit: int
    policy_company_query_limit: int
    report_context_min: int
    report_context_lookback_days: int
    long_term_trend_query_limit: int
    correlation_lookback_days: int
    correlation_min_abs: float
    source_news_limit: int
    monitor_event_lookback_hours: int
    monitor_event_limit: int
    news_locales: list[str]


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
        timezone=os.getenv("FINANCIAL_TIMEZONE", "Asia/Taipei"),
        keyword_limit=int(os.getenv("KEYWORD_LIMIT", "12")),
        keyword_query_limit=int(os.getenv("KEYWORD_QUERY_LIMIT", "8")),
        keyword_secondary_limit=int(os.getenv("KEYWORD_SECONDARY_LIMIT", "4")),
        keyword_retention_days=int(os.getenv("KEYWORD_RETENTION_DAYS", "14")),
        keyword_decay_factor=float(os.getenv("KEYWORD_DECAY_FACTOR", "0.85")),
        keyword_min_score=float(os.getenv("KEYWORD_MIN_SCORE", "1.0")),
        policy_query_limit=int(os.getenv("POLICY_QUERY_LIMIT", "8")),
        policy_company_query_limit=int(os.getenv("POLICY_COMPANY_QUERY_LIMIT", "8")),
        report_context_min=int(os.getenv("REPORT_CONTEXT_MIN", "3")),
        report_context_lookback_days=int(os.getenv("REPORT_CONTEXT_LOOKBACK_DAYS", "45")),
        long_term_trend_query_limit=int(os.getenv("LONG_TERM_TREND_QUERY_LIMIT", "6")),
        correlation_lookback_days=int(os.getenv("CORRELATION_LOOKBACK_DAYS", "90")),
        correlation_min_abs=float(os.getenv("CORRELATION_MIN_ABS", "0.45")),
        source_news_limit=int(os.getenv("SOURCE_NEWS_LIMIT", "20")),
        monitor_event_lookback_hours=int(os.getenv("MONITOR_EVENT_LOOKBACK_HOURS", "36")),
        monitor_event_limit=int(os.getenv("MONITOR_EVENT_LIMIT", "20")),
        news_locales=[locale.strip().upper() for locale in os.getenv("NEWS_LOCALES", "US,TW").split(",") if locale.strip()],
    )


def ensure_directories() -> None:
    for path in [
        CONFIG_DIR,
        DATA_DIR / "manual_notes",
        DATA_DIR / "market_snapshots",
        DATA_DIR / "news",
        OUTPUT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_symbols() -> list[dict]:
    with SYMBOLS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_symbols(symbols: list[dict]) -> None:
    with SYMBOLS_FILE.open("w", encoding="utf-8") as file:
        json.dump(symbols, file, indent=2)
        file.write("\n")


def load_keyword_weights() -> dict[str, int]:
    if not KEYWORD_WEIGHTS_FILE.exists():
        return {}
    with KEYWORD_WEIGHTS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_policy_keywords() -> dict:
    if not POLICY_KEYWORDS_FILE.exists():
        return {"terms": [], "company_terms": {}}
    with POLICY_KEYWORDS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_trend_keywords() -> dict[str, list[str]]:
    if not TREND_KEYWORDS_FILE.exists():
        return {}
    with TREND_KEYWORDS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_trend_monitors() -> dict:
    if not TREND_MONITORS_FILE.exists():
        return {}
    with TREND_MONITORS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_news_sources() -> list[dict]:
    if not NEWS_SOURCES_FILE.exists():
        return []
    with NEWS_SOURCES_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_correlation_pairs() -> list[dict]:
    if not CORRELATION_PAIRS_FILE.exists():
        return []
    with CORRELATION_PAIRS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)
