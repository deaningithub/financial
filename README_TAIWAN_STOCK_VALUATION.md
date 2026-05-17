# Taiwan Stock Valuation Workflow

This workflow keeps Taiwan stock research in local SQLite first.

```text
SQLite = source of truth
Google Sheet = optional display/export layer later
AI agents = read SQLite, write SQLite
```

The database file is ignored by git:

```text
data/taiwan_stock_valuation.db
```

## Initialize

Create the schema and seed the starter Taiwan stock list:

```powershell
python main.py taiwan-stocks init
python main.py taiwan-stocks list
```

Seeded stocks:

```text
2330 TSMC
2454 MediaTek
2317 Hon Hai Precision
2382 Quanta Computer
3231 Wistron
6669 Wiwynn
2409 AUO
4768 Onyx Healthcare Material
2313 Compeq Manufacturing
2308 Delta Electronics
```

## Import Data

Financial statement CSV columns:

```text
stock_id,year,quarter,revenue,gross_profit,operating_income,net_income,eps,total_assets,total_liabilities,equity,cash_and_equivalents,total_debt,operating_cash_flow,investing_cash_flow,financing_cash_flow,free_cash_flow,gross_margin,operating_margin,net_margin,roe,roa,source
```

Market price CSV columns:

```text
stock_id,trade_date,open_price,high_price,low_price,close_price,volume,market_cap,source
```

Import:

```powershell
python main.py taiwan-stocks import-financial-csv --path data\tw_financials.csv
python main.py taiwan-stocks import-price-csv --path data\tw_prices.csv
```

You can also enter one row manually:

```powershell
python main.py taiwan-stocks add-financial --stock-id 2409 --year 2025 --quarter 4 --revenue 61000 --net-income 1800 --eps 0.45 --equity 115000 --gross-margin 11.5 --operating-margin 4.1 --net-margin 3.0
python main.py taiwan-stocks add-price --stock-id 2409 --trade-date 2026-05-11 --close-price 18.5 --market-cap 178000
```

## Calculate Valuation

Calculate PE, PB, PS, ROE, growth, and first-pass fair value:

```powershell
python main.py taiwan-stocks calc-valuation --stock-id 2409 --calc-date 2026-05-11
```

The result is stored in `valuation_metrics`.

## Run LLM Agent Research

Set `OPENAI_API_KEY` in `.env`, your shell environment, GitHub Actions secrets, or Cloud Run Job environment variables. The code reads `OPENAI_API_KEY` through `load_settings()`, so deployment secrets are used automatically when present.

For GitHub Actions deployment, set these secrets at minimum:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

`OPENAI_MODEL` is optional and defaults to `gpt-5.5`.

Then run:

```powershell
python main.py taiwan-stocks run-research --stock-id 2409 --report-date 2026-05-11
```

This runs five database-backed agents:

```text
1. data_quality_agent
2. business_model_agent
3. valuation_method_agent
4. event_catalyst_agent
5. final_report_agent
```

Each round is stored in `ai_research_rounds`. The final report is stored in `final_reports` and also written to:

```text
outputs/taiwan_stock_2409_2026-05-11.md
```

For an offline deterministic run without OpenAI:

```powershell
python main.py taiwan-stocks run-research --stock-id 2409 --report-date 2026-05-11 --no-ai
```

## Read Reports

Read the latest final report from SQLite:

```powershell
python main.py taiwan-stocks show-report --stock-id 2409
```

Read a specific report date:

```powershell
python main.py taiwan-stocks show-report --stock-id 2409 --report-date 2026-05-11
```

Show only the rating and one-line summary:

```powershell
python main.py taiwan-stocks show-report --stock-id 2409 --summary
```

Read the five research rounds:

```powershell
python main.py taiwan-stocks show-rounds --stock-id 2409
```

Read the detailed round facts, assumptions, and risks:

```powershell
python main.py taiwan-stocks show-rounds --stock-id 2409 --details
```

You can also open the Markdown file directly from `outputs/`.

## Typical Full Flow

```powershell
python main.py taiwan-stocks init
python main.py taiwan-stocks import-financial-csv --path data\tw_financials.csv
python main.py taiwan-stocks import-price-csv --path data\tw_prices.csv
python main.py taiwan-stocks calc-valuation --stock-id 2409 --calc-date 2026-05-11
python main.py taiwan-stocks run-research --stock-id 2409 --report-date 2026-05-11
python main.py taiwan-stocks show-report --stock-id 2409 --report-date 2026-05-11 --summary
python main.py taiwan-stocks show-rounds --stock-id 2409 --details
```

## Notes

- The LLM agents only receive SQLite context and prior round outputs.
- They are instructed not to invent missing financial data.
- `financial_statements` should be treated as source data and should not be modified by agents.
- `valuation_metrics`, `ai_research_rounds`, and `final_reports` are generated layers.
- This is research infrastructure, not financial advice.
