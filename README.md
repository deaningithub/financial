# Daily Financial Intelligence System

This project turns your daily market notes, market numbers, and important news into a repeatable financial intelligence report.

It is not only "search the internet." The workflow is:

1. You add important news or keywords you care about.
2. The system updates market numbers for configured indexes, ETFs, stocks, FX, crypto, or rates.
3. It finds the biggest movers and trend changes.
4. It expands search keywords from your notes plus those anomalies.
5. It collects related news links.
6. It asks OpenAI to create a summary and risk assessment.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add:

```text
OPENAI_API_KEY=your_api_key_here
```

Optional:

```text
OPENAI_MODEL=gpt-5.5
```

## GitHub Codespaces

This repo includes a Codespaces dev container in `.devcontainer/devcontainer.json`.

1. Push this project to GitHub.
2. Open the repo on GitHub.
3. Choose `Code` -> `Codespaces` -> `Create codespace on main`.
4. Add your API key as a Codespaces secret named `OPENAI_API_KEY`.
5. In the Codespace terminal, run:

```bash
python main.py symbols
python main.py run
```

For a smoke test without OpenAI:

```bash
python main.py run --no-ai
```

Generated files are intentionally ignored:

- `data/financial_data.db`
- `data/market_snapshots/*.json`
- `data/news/*.json`
- `outputs/*.md`

## Daily Run

Add your human news notes:

```powershell
python main.py add-note --text "Fed officials sounded less dovish; Nvidia supplier guidance was strong."
```

Run the full pipeline:

```powershell
python main.py run
```

Output appears in:

- `outputs/daily_report_YYYY-MM-DD.md`
- `data/market_snapshots/YYYY-MM-DD.json`
- `data/news/YYYY-MM-DD.json`

The news search includes market anomalies, your weighted notes, historical secondary keywords, and political/company policy keywords. Long-term theme searches are only added when a monitored long-term trend crosses an attention threshold.
Each generated daily report is also saved into SQLite. Future reports use weighted keyword similarity to load at least three related historical reports as context, falling back to recent reports only when related matches are unavailable.

## Useful Commands

Show configured symbols:

```powershell
python main.py symbols
```

Add a symbol:

```powershell
python main.py add-symbol --symbol NVDA --name "Nvidia" --type stock --region US
```

Run without OpenAI, keeping the market/news collection:

```powershell
python main.py run --no-ai
```

## Configuration

Edit `config/symbols.json` to track the financial numbers you care about.
Edit `config/policy_keywords.json` to track political policy or company policy terms that can affect stocks.
Edit `config/trend_monitors.json` to track long-term themes such as AI chips, satellite communications, robotics/vehicles, and space exploration. These themes are monitored daily but only promoted into the report when their tracked symbols move enough.

The default list includes:

- S&P 500
- Nasdaq 100
- Russell 2000
- VIX
- US Dollar Index
- 10Y Treasury yield proxy
- Gold
- Oil
- Bitcoin
- A few large US stocks
- Sector representatives for healthcare, financials, energy, and consumer
- Europe, China, Hong Kong, Japan, and India index coverage
- Taiwan market status: TAIEX, Taiwan 50 ETF, TSMC, MediaTek, Hon Hai, UMC

The pipeline also creates dynamic short-term condition queries from market state, such as VIX stress, oil shocks, dollar/yield moves, and regional index selloffs or rallies.

Phase 2 analysis features:

- Cross-market correlation pairs are configured in `config/correlation_pairs.json`.
- Extra RSS news sources are configured in `config/news_sources.json`.
- Dynamic condition queries react to volatility, oil, dollar, yield, and regional index moves.
- AI reports receive correlation results so they can discuss synchronized moves and divergences across markets.

Policy search settings:

- `POLICY_QUERY_LIMIT=8`
- `POLICY_COMPANY_QUERY_LIMIT=8`
- `REPORT_CONTEXT_MIN=3`
- `REPORT_CONTEXT_LOOKBACK_DAYS=45`
- `LONG_TERM_TREND_QUERY_LIMIT=6`
- `CORRELATION_LOOKBACK_DAYS=90`
- `CORRELATION_MIN_ABS=0.45`
- `SOURCE_NEWS_LIMIT=20`

## Notes

- Market data uses `yfinance`.
- News discovery uses Google News RSS, so it does not need a separate news API key.
- The OpenAI step is skipped automatically if `OPENAI_API_KEY` is missing.
- This is an analysis assistant, not financial advice.
