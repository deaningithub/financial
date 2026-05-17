from __future__ import annotations

import csv
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "outputs"))
TAIWAN_STOCK_VALUATION_DB_PATH = DATA_DIR / "taiwan_stock_valuation.db"


def load_settings() -> SimpleNamespace:
    load_dotenv(ROOT / ".env")
    return SimpleNamespace(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
    )


TAIWAN_STOCK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    stock_id TEXT PRIMARY KEY,
    stock_name TEXT NOT NULL,
    market TEXT,
    industry TEXT,
    sub_industry TEXT,
    listing_date TEXT,
    status TEXT DEFAULT 'active',
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS financial_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,

    revenue REAL,
    gross_profit REAL,
    operating_income REAL,
    net_income REAL,
    eps REAL,

    total_assets REAL,
    total_liabilities REAL,
    equity REAL,
    cash_and_equivalents REAL,
    total_debt REAL,

    operating_cash_flow REAL,
    investing_cash_flow REAL,
    financing_cash_flow REAL,
    free_cash_flow REAL,

    gross_margin REAL,
    operating_margin REAL,
    net_margin REAL,
    roe REAL,
    roa REAL,

    source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(stock_id, year, quarter),
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS market_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL,
    trade_date TEXT NOT NULL,

    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume REAL,
    market_cap REAL,

    source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(stock_id, trade_date),
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS valuation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL,
    calc_date TEXT NOT NULL,

    close_price REAL,
    eps_ttm REAL,
    revenue_ttm REAL,
    book_value_per_share REAL,

    pe REAL,
    pb REAL,
    ps REAL,
    roe REAL,
    roa REAL,

    revenue_growth_yoy REAL,
    revenue_cagr_3y REAL,
    eps_growth_yoy REAL,
    eps_cagr_3y REAL,

    gross_margin_avg_3y REAL,
    operating_margin_avg_3y REAL,
    net_margin_avg_3y REAL,

    fair_value_bear REAL,
    fair_value_base REAL,
    fair_value_bull REAL,
    margin_of_safety REAL,

    valuation_method TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(stock_id, calc_date),
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS ai_research_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL,

    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',

    current_round INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 5,

    started_at TEXT,
    completed_at TEXT,
    failed_at TEXT,
    error_message TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS ai_research_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stock_id TEXT NOT NULL,
    task_id INTEGER,

    round_number INTEGER NOT NULL,
    agent_role TEXT NOT NULL,

    input_json TEXT,
    output_json TEXT,

    summary TEXT,
    key_facts TEXT,
    assumptions TEXT,
    risks TEXT,
    confidence_score REAL,

    model_name TEXT,
    prompt_version TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    FOREIGN KEY(task_id) REFERENCES ai_research_tasks(id)
);

CREATE TABLE IF NOT EXISTS final_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stock_id TEXT NOT NULL,
    report_date TEXT NOT NULL,

    rating TEXT,
    final_score REAL,

    title TEXT,
    one_line_summary TEXT,

    business_summary TEXT,
    financial_summary TEXT,
    valuation_summary TEXT,

    bull_case TEXT,
    base_case TEXT,
    bear_case TEXT,

    key_events TEXT,
    risk_factors TEXT,
    watch_keywords TEXT,

    fair_value_bear REAL,
    fair_value_base REAL,
    fair_value_bull REAL,

    current_price REAL,
    margin_of_safety REAL,

    report_markdown TEXT,
    report_html TEXT,

    human_review_status TEXT DEFAULT 'pending',
    human_note TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(stock_id, report_date),
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stock_id TEXT,
    event_date TEXT,
    event_type TEXT,

    title TEXT NOT NULL,
    summary TEXT,
    source_name TEXT,
    source_url TEXT,

    impact_direction TEXT,
    impact_score REAL,
    confidence_score REAL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS peer_companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stock_id TEXT NOT NULL,
    peer_stock_id TEXT NOT NULL,
    relationship_type TEXT,
    note TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(stock_id, peer_stock_id),
    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id),
    FOREIGN KEY(peer_stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    stock_id TEXT NOT NULL,
    watch_reason TEXT,
    target_price REAL,
    stop_loss_price REAL,

    status TEXT DEFAULT 'watching',
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    removed_at TEXT,

    FOREIGN KEY(stock_id) REFERENCES stocks(stock_id)
);

CREATE INDEX IF NOT EXISTS idx_financial_stock_period
ON financial_statements(stock_id, year, quarter);

CREATE INDEX IF NOT EXISTS idx_market_prices_stock_date
ON market_prices(stock_id, trade_date);

CREATE INDEX IF NOT EXISTS idx_valuation_stock_date
ON valuation_metrics(stock_id, calc_date);

CREATE INDEX IF NOT EXISTS idx_ai_tasks_status
ON ai_research_tasks(status, priority);

CREATE INDEX IF NOT EXISTS idx_ai_rounds_stock
ON ai_research_rounds(stock_id, round_number);

CREATE INDEX IF NOT EXISTS idx_final_reports_stock_date
ON final_reports(stock_id, report_date);
"""


TAIWAN_STOCK_SEEDS = [
    ("2330", "TSMC", "TWSE", "Semiconductors", "Foundry", "AI compute and advanced process leader"),
    ("2454", "MediaTek", "TWSE", "Semiconductors", "IC design", "Mobile SoC, edge AI, and communication chips"),
    ("2317", "Hon Hai Precision", "TWSE", "Electronics manufacturing", "EMS", "AI server, Apple supply chain, and EV manufacturing"),
    ("2382", "Quanta Computer", "TWSE", "Computer peripherals", "Servers", "AI server ODM"),
    ("3231", "Wistron", "TWSE", "Computer peripherals", "Servers", "AI server supply chain"),
    ("6669", "Wiwynn", "TWSE", "Computer peripherals", "Cloud servers", "High-purity cloud and AI server exposure"),
    ("2409", "AUO", "TWSE", "Optoelectronics", "Panels", "Cyclical panel stock for testing non-PE valuation judgment"),
    ("4768", "Onyx Healthcare Material", "TPEx", "Semiconductor materials", "Specialty chemicals", "Semiconductor materials and advanced process supply chain"),
    ("2313", "Compeq Manufacturing", "TWSE", "Electronic components", "PCB", "AI server, satellite, and high-end PCB supply chain"),
    ("2308", "Delta Electronics", "TWSE", "Electrical machinery", "Power and energy management", "AI data center power, thermal, and energy infrastructure"),
]


@dataclass(frozen=True)
class TaiwanStock:
    stock_id: str
    stock_name: str
    market: str | None
    industry: str | None
    sub_industry: str | None
    status: str
    note: str | None


@dataclass(frozen=True)
class ValuationResult:
    stock_id: str
    calc_date: str
    close_price: float | None
    eps_ttm: float | None
    revenue_ttm: float | None
    pe: float | None
    pb: float | None
    ps: float | None
    roe: float | None
    revenue_growth_yoy: float | None
    eps_growth_yoy: float | None
    fair_value_bear: float | None
    fair_value_base: float | None
    fair_value_bull: float | None
    margin_of_safety: float | None
    valuation_method: str


def connect_taiwan_stock_db(db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_taiwan_stock_valuation_db(
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
    seed_stocks: bool = True,
) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect_taiwan_stock_db(path) as connection:
        connection.executescript(TAIWAN_STOCK_SCHEMA_SQL)
        if seed_stocks:
            upsert_seed_stocks(connection)
        connection.commit()
    return path


def upsert_seed_stocks(connection: sqlite3.Connection) -> int:
    before = connection.total_changes
    connection.executemany(
        """
        INSERT INTO stocks
            (stock_id, stock_name, market, industry, sub_industry, note, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(stock_id) DO UPDATE SET
            stock_name = excluded.stock_name,
            market = excluded.market,
            industry = excluded.industry,
            sub_industry = excluded.sub_industry,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """,
        TAIWAN_STOCK_SEEDS,
    )
    return connection.total_changes - before


def list_taiwan_stocks(
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> list[TaiwanStock]:
    with connect_taiwan_stock_db(db_path) as connection:
        rows = connection.execute(
            """
            SELECT stock_id, stock_name, market, industry, sub_industry, status, note
            FROM stocks
            ORDER BY stock_id
            """
        ).fetchall()
    return [
        TaiwanStock(
            stock_id=row["stock_id"],
            stock_name=row["stock_name"],
            market=row["market"],
            industry=row["industry"],
            sub_industry=row["sub_industry"],
            status=row["status"],
            note=row["note"],
        )
        for row in rows
    ]


def add_taiwan_stock(
    stock_id: str,
    stock_name: str,
    market: str | None = None,
    industry: str | None = None,
    sub_industry: str | None = None,
    note: str | None = None,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> None:
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    with connect_taiwan_stock_db(db_path) as connection:
        connection.execute(
            """
            INSERT INTO stocks
                (stock_id, stock_name, market, industry, sub_industry, note, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(stock_id) DO UPDATE SET
                stock_name = excluded.stock_name,
                market = excluded.market,
                industry = excluded.industry,
                sub_industry = excluded.sub_industry,
                note = excluded.note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (stock_id, stock_name, market, industry, sub_industry, note),
        )
        connection.commit()


def create_ai_research_task(
    stock_id: str,
    task_type: str = "full_research",
    priority: int = 5,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> int:
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    with connect_taiwan_stock_db(db_path) as connection:
        stock = connection.execute(
            "SELECT stock_id FROM stocks WHERE stock_id = ?",
            (stock_id,),
        ).fetchone()
        if stock is None:
            raise ValueError(f"Unknown Taiwan stock: {stock_id}")
        cursor = connection.execute(
            """
            INSERT INTO ai_research_tasks
                (stock_id, task_type, status, priority, updated_at)
            VALUES (?, ?, 'pending', ?, CURRENT_TIMESTAMP)
            """,
            (stock_id, task_type, priority),
        )
        connection.commit()
        return int(cursor.lastrowid)


def get_final_report(
    stock_id: str,
    report_date: str | None = None,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> dict[str, Any] | None:
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    query = "SELECT * FROM final_reports WHERE stock_id = ?"
    params: list[Any] = [stock_id]
    if report_date:
        query += " AND report_date = ?"
        params.append(report_date)
    query += " ORDER BY report_date DESC LIMIT 1"
    with connect_taiwan_stock_db(db_path) as connection:
        row = connection.execute(query, params).fetchone()
    return dict(row) if row else None


def list_ai_research_rounds(
    stock_id: str,
    task_id: int | None = None,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> list[dict[str, Any]]:
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    query = "SELECT * FROM ai_research_rounds WHERE stock_id = ?"
    params: list[Any] = [stock_id]
    if task_id is not None:
        query += " AND task_id = ?"
        params.append(task_id)
    query += " ORDER BY task_id DESC, round_number ASC"
    with connect_taiwan_stock_db(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def upsert_financial_statement(
    stock_id: str,
    year: int,
    quarter: int,
    values: dict[str, float | str | None],
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> None:
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    allowed_columns = [
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "eps",
        "total_assets",
        "total_liabilities",
        "equity",
        "cash_and_equivalents",
        "total_debt",
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
        "free_cash_flow",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "roe",
        "roa",
        "source",
    ]
    payload = {column: values.get(column) for column in allowed_columns}
    columns = ["stock_id", "year", "quarter", *allowed_columns, "updated_at"]
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(
        f"{column} = excluded.{column}" for column in [*allowed_columns, "updated_at"]
    )
    with connect_taiwan_stock_db(db_path) as connection:
        _ensure_stock_exists(connection, stock_id)
        connection.execute(
            f"""
            INSERT INTO financial_statements ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(stock_id, year, quarter) DO UPDATE SET {update_clause}
            """,
            (
                stock_id,
                year,
                quarter,
                *(payload[column] for column in allowed_columns),
                _now_sql(),
            ),
        )
        connection.commit()


def upsert_market_price(
    stock_id: str,
    trade_date: str,
    values: dict[str, float | str | None],
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> None:
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    allowed_columns = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "market_cap",
        "source",
    ]
    payload = {column: values.get(column) for column in allowed_columns}
    columns = ["stock_id", "trade_date", *allowed_columns]
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column} = excluded.{column}" for column in allowed_columns)
    with connect_taiwan_stock_db(db_path) as connection:
        _ensure_stock_exists(connection, stock_id)
        connection.execute(
            f"""
            INSERT INTO market_prices ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(stock_id, trade_date) DO UPDATE SET {update_clause}
            """,
            (
                stock_id,
                trade_date,
                *(payload[column] for column in allowed_columns),
            ),
        )
        connection.commit()


def import_financial_statements_csv(
    csv_path: Path | str,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> int:
    imported = 0
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            stock_id = (row.get("stock_id") or "").strip()
            year = _int_from_row(row, "year")
            quarter = _int_from_row(row, "quarter")
            if not stock_id or year is None or quarter is None:
                continue
            upsert_financial_statement(
                stock_id=stock_id,
                year=year,
                quarter=quarter,
                values={key: _csv_value(value) for key, value in row.items()},
                db_path=db_path,
            )
            imported += 1
    return imported


def import_market_prices_csv(
    csv_path: Path | str,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> int:
    imported = 0
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            stock_id = (row.get("stock_id") or "").strip()
            trade_date = (row.get("trade_date") or "").strip()
            if not stock_id or not trade_date:
                continue
            upsert_market_price(
                stock_id=stock_id,
                trade_date=trade_date,
                values={key: _csv_value(value) for key, value in row.items()},
                db_path=db_path,
            )
            imported += 1
    return imported


def calculate_valuation_metrics(
    stock_id: str,
    calc_date: str | None = None,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> ValuationResult:
    calc_date = calc_date or date.today().isoformat()
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    with connect_taiwan_stock_db(db_path) as connection:
        _ensure_stock_exists(connection, stock_id)
        price = connection.execute(
            """
            SELECT close_price, market_cap
            FROM market_prices
            WHERE stock_id = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (stock_id, calc_date),
        ).fetchone()
        financials = connection.execute(
            """
            SELECT *
            FROM financial_statements
            WHERE stock_id = ?
            ORDER BY year DESC, quarter DESC
            LIMIT 16
            """,
            (stock_id,),
        ).fetchall()
        if not financials:
            raise ValueError(f"No financial statements found for Taiwan stock: {stock_id}")

        latest_four = list(financials[:4])
        latest = financials[0]
        previous_same_quarter = _find_previous_same_quarter(financials, latest["year"], latest["quarter"])

        close_price = _float_or_none(price["close_price"]) if price else None
        market_cap = _float_or_none(price["market_cap"]) if price else None
        eps_ttm = _sum_present(row["eps"] for row in latest_four)
        revenue_ttm = _sum_present(row["revenue"] for row in latest_four)
        net_income_ttm = _sum_present(row["net_income"] for row in latest_four)
        equity = _float_or_none(latest["equity"])

        pe = _safe_div(close_price, eps_ttm)
        pb = _safe_div(market_cap, equity)
        ps = _safe_div(market_cap, revenue_ttm)
        roe = _float_or_none(latest["roe"])
        if roe is None:
            roe = _safe_pct(net_income_ttm, equity)
        roa = _float_or_none(latest["roa"])
        if roa is None:
            roa = _safe_pct(net_income_ttm, _float_or_none(latest["total_assets"]))

        revenue_growth_yoy = None
        eps_growth_yoy = None
        if previous_same_quarter is not None:
            revenue_growth_yoy = _growth_pct(latest["revenue"], previous_same_quarter["revenue"])
            eps_growth_yoy = _growth_pct(latest["eps"], previous_same_quarter["eps"])

        revenue_cagr_3y = _period_cagr(financials, "revenue", years=3)
        eps_cagr_3y = _period_cagr(financials, "eps", years=3)
        gross_margin_avg_3y = _avg_present(row["gross_margin"] for row in financials[:12])
        operating_margin_avg_3y = _avg_present(row["operating_margin"] for row in financials[:12])
        net_margin_avg_3y = _avg_present(row["net_margin"] for row in financials[:12])

        valuation_method, fair_value_bear, fair_value_base, fair_value_bull = _estimate_fair_value(
            close_price=close_price,
            eps_ttm=eps_ttm,
            book_value_per_share=None,
            roe=roe,
            revenue_growth_yoy=revenue_growth_yoy,
        )
        margin_of_safety = None
        if close_price is not None and fair_value_base is not None and fair_value_base != 0:
            margin_of_safety = (fair_value_base - close_price) / fair_value_base * 100

        connection.execute(
            """
            INSERT INTO valuation_metrics (
                stock_id, calc_date, close_price, eps_ttm, revenue_ttm,
                book_value_per_share, pe, pb, ps, roe, roa,
                revenue_growth_yoy, revenue_cagr_3y, eps_growth_yoy, eps_cagr_3y,
                gross_margin_avg_3y, operating_margin_avg_3y, net_margin_avg_3y,
                fair_value_bear, fair_value_base, fair_value_bull,
                margin_of_safety, valuation_method
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_id, calc_date) DO UPDATE SET
                close_price = excluded.close_price,
                eps_ttm = excluded.eps_ttm,
                revenue_ttm = excluded.revenue_ttm,
                book_value_per_share = excluded.book_value_per_share,
                pe = excluded.pe,
                pb = excluded.pb,
                ps = excluded.ps,
                roe = excluded.roe,
                roa = excluded.roa,
                revenue_growth_yoy = excluded.revenue_growth_yoy,
                revenue_cagr_3y = excluded.revenue_cagr_3y,
                eps_growth_yoy = excluded.eps_growth_yoy,
                eps_cagr_3y = excluded.eps_cagr_3y,
                gross_margin_avg_3y = excluded.gross_margin_avg_3y,
                operating_margin_avg_3y = excluded.operating_margin_avg_3y,
                net_margin_avg_3y = excluded.net_margin_avg_3y,
                fair_value_bear = excluded.fair_value_bear,
                fair_value_base = excluded.fair_value_base,
                fair_value_bull = excluded.fair_value_bull,
                margin_of_safety = excluded.margin_of_safety,
                valuation_method = excluded.valuation_method
            """,
            (
                stock_id,
                calc_date,
                close_price,
                eps_ttm,
                revenue_ttm,
                None,
                pe,
                pb,
                ps,
                roe,
                roa,
                revenue_growth_yoy,
                revenue_cagr_3y,
                eps_growth_yoy,
                eps_cagr_3y,
                gross_margin_avg_3y,
                operating_margin_avg_3y,
                net_margin_avg_3y,
                fair_value_bear,
                fair_value_base,
                fair_value_bull,
                margin_of_safety,
                valuation_method,
            ),
        )
        connection.commit()

    return ValuationResult(
        stock_id=stock_id,
        calc_date=calc_date,
        close_price=close_price,
        eps_ttm=eps_ttm,
        revenue_ttm=revenue_ttm,
        pe=pe,
        pb=pb,
        ps=ps,
        roe=roe,
        revenue_growth_yoy=revenue_growth_yoy,
        eps_growth_yoy=eps_growth_yoy,
        fair_value_bear=fair_value_bear,
        fair_value_base=fair_value_base,
        fair_value_bull=fair_value_bull,
        margin_of_safety=margin_of_safety,
        valuation_method=valuation_method,
    )


def run_taiwan_stock_research(
    stock_id: str,
    task_id: int | None = None,
    report_date: str | None = None,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
    use_ai: bool = True,
    api_key: str | None = None,
    model: str | None = None,
) -> Path:
    report_date = report_date or date.today().isoformat()
    settings = load_settings()
    api_key = api_key if api_key is not None else settings.openai_api_key
    model = model or settings.openai_model
    init_taiwan_stock_valuation_db(db_path, seed_stocks=False)
    with connect_taiwan_stock_db(db_path) as connection:
        stock = _ensure_stock_exists(connection, stock_id)
        if task_id is None:
            task_id = create_ai_research_task(stock_id, db_path=db_path)
        connection.execute(
            """
            UPDATE ai_research_tasks
            SET status = 'running', started_at = COALESCE(started_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (task_id,),
        )
        valuation = _latest_valuation(connection, stock_id)
        financials = connection.execute(
            """
            SELECT * FROM financial_statements
            WHERE stock_id = ?
            ORDER BY year DESC, quarter DESC
            LIMIT 8
            """,
            (stock_id,),
        ).fetchall()
        events = connection.execute(
            """
            SELECT * FROM news_events
            WHERE stock_id = ? OR stock_id IS NULL
            ORDER BY event_date DESC, id DESC
            LIMIT 12
            """,
            (stock_id,),
        ).fetchall()

        context = {
            "stock": dict(stock),
            "valuation": dict(valuation) if valuation else {},
            "financial_periods": [dict(row) for row in financials],
            "events": [dict(row) for row in events],
        }
        try:
            if use_ai and api_key:
                rounds = _build_llm_research_rounds(context, api_key=api_key, model=model)
                model_name = model
            else:
                rounds = _build_research_rounds(context)
                model_name = "rule-based-v1"
        except Exception as exc:
            connection.execute(
                """
                UPDATE ai_research_tasks
                SET status = 'failed', failed_at = CURRENT_TIMESTAMP, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (str(exc), task_id),
            )
            connection.commit()
            raise
        connection.execute("DELETE FROM ai_research_rounds WHERE task_id = ?", (task_id,))
        for round_payload in rounds:
            connection.execute(
                """
                INSERT INTO ai_research_rounds (
                    stock_id, task_id, round_number, agent_role,
                    input_json, output_json, summary, key_facts, assumptions, risks,
                    confidence_score, model_name, prompt_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stock_id,
                    task_id,
                    round_payload["round_number"],
                    round_payload["agent_role"],
                    _json_dump(context),
                    _json_dump(round_payload),
                    round_payload["summary"],
                    "\n".join(round_payload["key_facts"]),
                    "\n".join(round_payload["assumptions"]),
                    "\n".join(round_payload["risks"]),
                    round_payload["confidence_score"],
                    round_payload.get("model_name") or model_name,
                    "taiwan-stock-v1",
                ),
            )
            connection.execute(
                "UPDATE ai_research_tasks SET current_round = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (round_payload["round_number"], task_id),
            )

        final_report = _build_final_report(stock, valuation, rounds, report_date)
        connection.execute(
            """
            INSERT INTO final_reports (
                stock_id, report_date, rating, final_score, title, one_line_summary,
                business_summary, financial_summary, valuation_summary,
                bull_case, base_case, bear_case, key_events, risk_factors, watch_keywords,
                fair_value_bear, fair_value_base, fair_value_bull,
                current_price, margin_of_safety, report_markdown, human_review_status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            ON CONFLICT(stock_id, report_date) DO UPDATE SET
                rating = excluded.rating,
                final_score = excluded.final_score,
                title = excluded.title,
                one_line_summary = excluded.one_line_summary,
                business_summary = excluded.business_summary,
                financial_summary = excluded.financial_summary,
                valuation_summary = excluded.valuation_summary,
                bull_case = excluded.bull_case,
                base_case = excluded.base_case,
                bear_case = excluded.bear_case,
                key_events = excluded.key_events,
                risk_factors = excluded.risk_factors,
                watch_keywords = excluded.watch_keywords,
                fair_value_bear = excluded.fair_value_bear,
                fair_value_base = excluded.fair_value_base,
                fair_value_bull = excluded.fair_value_bull,
                current_price = excluded.current_price,
                margin_of_safety = excluded.margin_of_safety,
                report_markdown = excluded.report_markdown,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                stock_id,
                report_date,
                final_report["rating"],
                final_report["final_score"],
                final_report["title"],
                final_report["one_line_summary"],
                final_report["business_summary"],
                final_report["financial_summary"],
                final_report["valuation_summary"],
                final_report["bull_case"],
                final_report["base_case"],
                final_report["bear_case"],
                final_report["key_events"],
                final_report["risk_factors"],
                final_report["watch_keywords"],
                _row_get(valuation, "fair_value_bear"),
                _row_get(valuation, "fair_value_base"),
                _row_get(valuation, "fair_value_bull"),
                _row_get(valuation, "close_price"),
                _row_get(valuation, "margin_of_safety"),
                final_report["report_markdown"],
            ),
        )
        connection.execute(
            """
            UPDATE ai_research_tasks
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (task_id,),
        )
        connection.commit()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"taiwan_stock_{stock_id}_{report_date}.md"
    report_path.write_text(final_report["report_markdown"], encoding="utf-8")
    return report_path


def run_rule_based_research(
    stock_id: str,
    task_id: int | None = None,
    report_date: str | None = None,
    db_path: Path | str = TAIWAN_STOCK_VALUATION_DB_PATH,
) -> Path:
    return run_taiwan_stock_research(
        stock_id=stock_id,
        task_id=task_id,
        report_date=report_date,
        db_path=db_path,
        use_ai=False,
    )


def _ensure_stock_exists(connection: sqlite3.Connection, stock_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM stocks WHERE stock_id = ?",
        (stock_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown Taiwan stock: {stock_id}")
    return row


def _now_sql() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _sum_present(values: Any) -> float | None:
    numbers = [_float_or_none(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if not numbers:
        return None
    return sum(numbers)


def _avg_present(values: Any) -> float | None:
    numbers = [_float_or_none(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _safe_pct(numerator: float | None, denominator: float | None) -> float | None:
    value = _safe_div(numerator, denominator)
    if value is None:
        return None
    return value * 100


def _growth_pct(current: Any, previous: Any) -> float | None:
    current_value = _float_or_none(current)
    previous_value = _float_or_none(previous)
    if current_value is None or previous_value in (None, 0):
        return None
    return (current_value - previous_value) / abs(previous_value) * 100


def _find_previous_same_quarter(
    rows: list[sqlite3.Row],
    latest_year: int,
    latest_quarter: int,
) -> sqlite3.Row | None:
    for row in rows:
        if row["year"] == latest_year - 1 and row["quarter"] == latest_quarter:
            return row
    return None


def _period_cagr(rows: list[sqlite3.Row], column: str, years: int) -> float | None:
    latest = rows[0] if rows else None
    if latest is None:
        return None
    target_year = int(latest["year"]) - years
    target_quarter = int(latest["quarter"])
    previous = None
    for row in rows:
        if int(row["year"]) == target_year and int(row["quarter"]) == target_quarter:
            previous = row
            break
    if previous is None:
        return None
    current_value = _float_or_none(latest[column])
    previous_value = _float_or_none(previous[column])
    if current_value is None or previous_value is None or previous_value <= 0 or current_value <= 0:
        return None
    return ((current_value / previous_value) ** (1 / years) - 1) * 100


def _estimate_fair_value(
    close_price: float | None,
    eps_ttm: float | None,
    book_value_per_share: float | None,
    roe: float | None,
    revenue_growth_yoy: float | None,
) -> tuple[str, float | None, float | None, float | None]:
    if eps_ttm is not None and eps_ttm > 0:
        if revenue_growth_yoy is not None and revenue_growth_yoy > 20:
            multiples = (14.0, 18.0, 22.0)
        elif revenue_growth_yoy is not None and revenue_growth_yoy < -10:
            multiples = (8.0, 11.0, 14.0)
        elif roe is not None and roe > 15:
            multiples = (12.0, 16.0, 20.0)
        else:
            multiples = (10.0, 13.0, 16.0)
        return "pe_ttm_rule_based", *(eps_ttm * multiple for multiple in multiples)
    if book_value_per_share is not None and book_value_per_share > 0:
        return "pb_cycle_rule_based", book_value_per_share * 0.8, book_value_per_share * 1.1, book_value_per_share * 1.5
    if close_price is not None:
        return "price_anchor_insufficient_data", close_price * 0.8, close_price, close_price * 1.2
    return "insufficient_data", None, None, None


def _latest_valuation(connection: sqlite3.Connection, stock_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM valuation_metrics
        WHERE stock_id = ?
        ORDER BY calc_date DESC
        LIMIT 1
        """,
        (stock_id,),
    ).fetchone()


LLM_ROUND_SPECS = [
    {
        "round_number": 1,
        "agent_role": "data_quality_agent",
        "instruction": (
            "Check whether the financial statements, prices, and valuation inputs are sufficient. "
            "Identify missing periods, abnormal EPS or margin patterns, cash-flow issues, and whether the stock can enter valuation."
        ),
    },
    {
        "round_number": 2,
        "agent_role": "business_model_agent",
        "instruction": (
            "Analyze how the company makes money, its main products, customers, industry position, moat, cyclicality, and likely peers."
        ),
    },
    {
        "round_number": 3,
        "agent_role": "valuation_method_agent",
        "instruction": (
            "Choose the suitable valuation method among PE, PB, PS, DCF, or event-driven valuation. "
            "Explain reasonable multiple ranges, assumptions, and methods that should not be used."
        ),
    },
    {
        "round_number": 4,
        "agent_role": "event_catalyst_agent",
        "instruction": (
            "Identify likely 3-month, 6-month, and 12-month catalysts, positive drivers, negative risks, and tracking keywords."
        ),
    },
    {
        "round_number": 5,
        "agent_role": "final_report_agent",
        "instruction": (
            "Synthesize the prior rounds into a final investment research draft with rating, fair value range, scenarios, risks, and watchlist view."
        ),
    },
]


def _build_llm_research_rounds(
    context: dict[str, Any],
    api_key: str,
    model: str,
) -> list[dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    rounds: list[dict[str, Any]] = []
    for spec in LLM_ROUND_SPECS:
        payload = _call_llm_research_agent(
            client=client,
            model=model,
            context=context,
            previous_rounds=rounds,
            round_number=spec["round_number"],
            agent_role=spec["agent_role"],
            instruction=spec["instruction"],
        )
        payload["round_number"] = spec["round_number"]
        payload["agent_role"] = spec["agent_role"]
        payload["model_name"] = model
        rounds.append(_normalize_round_payload(payload))
    return rounds


def _call_llm_research_agent(
    client: Any,
    model: str,
    context: dict[str, Any],
    previous_rounds: list[dict[str, Any]],
    round_number: int,
    agent_role: str,
    instruction: str,
) -> dict[str, Any]:
    system_prompt = (
        "You are a Taiwan stock valuation research agent. "
        "Use only the provided SQLite context and previous round outputs. "
        "Do not invent missing financial data. If data is incomplete, say so. "
        "This is research workflow output, not financial advice. "
        "Return one valid JSON object only."
    )
    user_prompt = f"""
Round: {round_number}
Agent role: {agent_role}
Task: {instruction}

Required JSON keys:
- summary: string
- key_facts: array of strings
- assumptions: array of strings
- risks: array of strings
- confidence_score: number between 0 and 1
- rating: optional string, one of strong_buy,buy,watch,hold,avoid
- final_score: optional number between 0 and 100
- one_line_summary: optional string
- business_summary: optional string
- financial_summary: optional string
- valuation_summary: optional string
- bull_case: optional string
- base_case: optional string
- bear_case: optional string
- key_events: optional string
- watch_keywords: optional string

SQLite context:
{_json_dump(context)}

Previous round outputs:
{_json_dump(previous_rounds)}
"""
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return _parse_json_object(response.output_text)


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM agent did not return a JSON object")
    return parsed


def _normalize_round_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["summary"] = str(normalized.get("summary") or "")
    normalized["key_facts"] = _string_list(normalized.get("key_facts"))
    normalized["assumptions"] = _string_list(normalized.get("assumptions"))
    normalized["risks"] = _string_list(normalized.get("risks"))
    try:
        confidence = float(normalized.get("confidence_score", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    normalized["confidence_score"] = max(0.0, min(1.0, confidence))
    return normalized


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _build_research_rounds(context: dict[str, Any]) -> list[dict[str, Any]]:
    stock = context["stock"]
    valuation = context.get("valuation", {})
    financials = context.get("financial_periods", [])
    has_financials = bool(financials)
    has_valuation = bool(valuation)
    stock_label = f"{stock['stock_id']} {stock['stock_name']}"
    return [
        {
            "round_number": 1,
            "agent_role": "data_quality_agent",
            "summary": f"{stock_label} data quality check completed with {'financial data available' if has_financials else 'missing financial data'}.",
            "key_facts": [
                f"Financial periods loaded: {len(financials)}",
                f"Latest valuation exists: {has_valuation}",
            ],
            "assumptions": ["Manual or semi-automated data is treated as source-of-record until collectors are added."],
            "risks": ["Incomplete statements can distort TTM and growth calculations."],
            "confidence_score": 0.72 if has_financials else 0.35,
        },
        {
            "round_number": 2,
            "agent_role": "business_model_agent",
            "summary": f"{stock_label} business model classified under {stock.get('industry') or 'unknown industry'} / {stock.get('sub_industry') or 'unknown sub-industry'}.",
            "key_facts": [stock.get("note") or "No business note provided."],
            "assumptions": ["Industry classification is based on the stock master record."],
            "risks": ["Customer concentration and cycle exposure require human or news validation."],
            "confidence_score": 0.62,
        },
        {
            "round_number": 3,
            "agent_role": "valuation_method_agent",
            "summary": f"Selected valuation method: {valuation.get('valuation_method') or 'insufficient_data'}.",
            "key_facts": [
                f"PE: {_fmt(valuation.get('pe'))}",
                f"PB: {_fmt(valuation.get('pb'))}",
                f"ROE: {_fmt(valuation.get('roe'))}",
            ],
            "assumptions": ["Fair value is a first-pass rule-based range, not a finished investment conclusion."],
            "risks": ["Cyclical stocks may require PB/asset-cycle work instead of a simple PE model."],
            "confidence_score": 0.66 if has_valuation else 0.30,
        },
        {
            "round_number": 4,
            "agent_role": "event_catalyst_agent",
            "summary": "Catalyst scan prepared from stored news_events and watch keywords.",
            "key_facts": [f"Stored event count in context: {len(context.get('events', []))}"],
            "assumptions": ["No external live news collection is performed inside this MVP research command."],
            "risks": ["Near-term catalysts may be stale until news_events ingestion is connected."],
            "confidence_score": 0.50,
        },
        {
            "round_number": 5,
            "agent_role": "final_report_agent",
            "summary": f"Generated final report draft for {stock_label}.",
            "key_facts": [
                f"Fair value base: {_fmt(valuation.get('fair_value_base'))}",
                f"Margin of safety: {_fmt(valuation.get('margin_of_safety'))}",
            ],
            "assumptions": ["Human review is required before using the report for portfolio action."],
            "risks": ["The report is a database workflow test until real financial and event data are complete."],
            "confidence_score": 0.60 if has_valuation else 0.32,
        },
    ]


def _build_final_report(
    stock: sqlite3.Row,
    valuation: sqlite3.Row | None,
    rounds: list[dict[str, Any]],
    report_date: str,
) -> dict[str, Any]:
    margin = _row_get(valuation, "margin_of_safety")
    final_round = rounds[-1] if rounds else {}
    rating, score = _rating_from_margin(margin)
    if final_round.get("rating"):
        rating = str(final_round["rating"])
    if final_round.get("final_score") is not None:
        try:
            score = float(final_round["final_score"])
        except (TypeError, ValueError):
            pass
    title = f"{stock['stock_id']} {stock['stock_name']} Taiwan stock valuation draft - {report_date}"
    one_line = str(final_round.get("one_line_summary") or "").strip() or (
        f"{stock['stock_name']} rating is {rating}. "
        "This is a SQLite MVP research draft and requires human review."
    )
    business_summary = str(final_round.get("business_summary") or "").strip() or (
        f"{stock['stock_name']} is classified as "
        f"{stock['industry'] or 'uncategorized'} / {stock['sub_industry'] or 'uncategorized'}. "
        f"{stock['note'] or ''}"
    ).strip()
    financial_summary = str(final_round.get("financial_summary") or "").strip() or (
        f"TTM EPS={_fmt(_row_get(valuation, 'eps_ttm'))}, "
        f"TTM revenue={_fmt(_row_get(valuation, 'revenue_ttm'))}, "
        f"ROE={_fmt(_row_get(valuation, 'roe'))}."
    )
    valuation_summary = str(final_round.get("valuation_summary") or "").strip() or (
        f"method={_row_get(valuation, 'valuation_method') or 'insufficient_data'}, "
        f"bear/base/bull={_fmt(_row_get(valuation, 'fair_value_bear'))}/"
        f"{_fmt(_row_get(valuation, 'fair_value_base'))}/"
        f"{_fmt(_row_get(valuation, 'fair_value_bull'))}, "
        f"margin_of_safety={_fmt(margin)}."
    )
    risk_factors = "\n".join(risk for item in rounds for risk in item["risks"])
    watch_keywords = ", ".join(
        keyword
        for keyword in [
            stock["stock_name"],
            stock["industry"],
            stock["sub_industry"],
            "earnings",
            "investor conference",
            "gross margin",
            "inventory",
        ]
        if keyword
    )
    if final_round.get("watch_keywords"):
        watch_keywords = str(final_round["watch_keywords"])
    round_lines = [
        f"- Round {item['round_number']} {item['agent_role']}: {item['summary']}"
        for item in rounds
    ]
    report_markdown = "\n".join(
        [
            f"# {title}",
            "",
            f"One-line conclusion: {one_line}",
            "",
            "## Valuation Summary",
            valuation_summary,
            "",
            "## Business Model",
            business_summary,
            "",
            "## Financial Summary",
            financial_summary,
            "",
            "## Bull / Base / Bear",
            f"- Bull: {str(final_round.get('bull_case') or 'Demand recovers, margins improve, and valuation multiples rerate.')}",
            f"- Base: {str(final_round.get('base_case') or 'Operations stabilize or improve gradually while more financial data is collected.')}",
            f"- Bear: {str(final_round.get('bear_case') or 'Cycle pressure, price competition, inventory risk, or capex pressure worsens.')}",
            "",
            "## AI Research Rounds",
            *round_lines,
            "",
            "## Risks",
            risk_factors,
            "",
            "_This report is for research workflow testing and is not financial advice._",
            "",
        ]
    )
    return {
        "rating": rating,
        "final_score": score,
        "title": title,
        "one_line_summary": one_line,
        "business_summary": business_summary,
        "financial_summary": financial_summary,
        "valuation_summary": valuation_summary,
        "bull_case": str(final_round.get("bull_case") or "Demand recovers, margins improve, and valuation multiples rerate."),
        "base_case": str(final_round.get("base_case") or "Operations stabilize or improve gradually while more financial data is collected."),
        "bear_case": str(final_round.get("bear_case") or "Cycle pressure, price competition, inventory risk, or capex pressure worsens."),
        "key_events": str(final_round.get("key_events") or "Investor conference, monthly revenue, quarterly results, inventory cycle, end-demand indicators."),
        "risk_factors": risk_factors,
        "watch_keywords": watch_keywords,
        "report_markdown": report_markdown,
    }


def _rating_from_margin(margin_of_safety: float | None) -> tuple[str, float]:
    if margin_of_safety is None:
        return "watch", 50.0
    if margin_of_safety >= 30:
        return "strong_buy", 85.0
    if margin_of_safety >= 15:
        return "buy", 75.0
    if margin_of_safety >= 0:
        return "watch", 62.0
    if margin_of_safety >= -20:
        return "hold", 48.0
    return "avoid", 30.0


def _row_get(row: sqlite3.Row | None | dict[str, Any], key: str) -> Any:
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _json_dump(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


def _csv_value(value: Any) -> float | str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return value.strip()


def _int_from_row(row: dict[str, Any], key: str) -> int | None:
    value = _csv_value(row.get(key))
    if value is None:
        return None
    return int(float(value))
