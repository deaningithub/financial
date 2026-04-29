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

The news search includes market anomalies, your weighted notes, historical secondary keywords, and political/company policy keywords.

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
- Taiwan market status: TAIEX, Taiwan 50 ETF, TSMC, MediaTek, Hon Hai, UMC

Policy search settings:

- `POLICY_QUERY_LIMIT=8`
- `POLICY_COMPANY_QUERY_LIMIT=8`

## Notes

- Market data uses `yfinance`.
- News discovery uses Google News RSS, so it does not need a separate news API key.
- The OpenAI step is skipped automatically if `OPENAI_API_KEY` is missing.
- This is an analysis assistant, not financial advice.
