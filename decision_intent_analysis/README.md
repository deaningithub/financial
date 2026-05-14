# Decision Intent Analysis

This is a standalone subproject for analyzing likely decision intent behind U.S. policy and major U.S. technology-company decisions.

It is designed to be split into its own GitHub repository. By default, it reuses the parent financial system SQLite database:

```text
../data/financial_data.db
```

You can override that path with:

```text
FINANCIAL_DB_PATH=/path/to/financial_data.db
```

## Purpose

The project turns scattered daily signals into testable hypotheses about decision intent, especially:

- White House policy direction
- Pentagon / Department of Defense procurement and supply-chain priorities
- Apple order and supply-chain decisions that can affect TSMC and Taiwan suppliers
- Nvidia AI accelerator, export-control, TSMC, CoWoS, and HBM strategy
- U.S. hyperscaler AI capex, data-center, custom silicon, and Taiwan investment behavior

## Guardrail

This project does not claim to know private motives.

It produces evidence-bound hypotheses:

```text
observable signals -> plausible objective -> confidence -> what would confirm or falsify it
```

Read the output as scenario analysis, not proof of hidden intent.

## Setup

```powershell
cd decision_intent_analysis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Optional OpenAI overlay:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.5
```

## Commands

List configured actors:

```powershell
python main.py actors
```

Run the deterministic report:

```powershell
python main.py run --date 2026-05-14 --no-ai
```

Run with the optional OpenAI overlay:

```powershell
python main.py run --date 2026-05-14
```

Limit to specific actors:

```powershell
python main.py run --actors white_house apple nvidia --lookback-days 21
```

Output appears in:

```text
outputs/intent_report_YYYY-MM-DD.md
```

## Current Actors

- `white_house`
- `pentagon`
- `apple`
- `nvidia`
- `hyperscalers`

## Evidence Sources

The project reads existing tables from `financial_data.db`:

- `news_items`: collected news headlines and links
- `daily_reports`: prior generated reports and AI summaries
- `monitor_events`: external alert bridge events

Future versions can add explicit policy calendars, official White House / Commerce / DoD feeds, earnings-call transcripts, and corporate capex history.

## Interpretation Method

Each actor has:

- keywords
- likely objectives
- watch markers
- counter-evidence requirements

The report ranks evidence, picks the most supported objective, assigns confidence, then lists what to watch next and what would falsify the hypothesis.

Confidence is intentionally conservative. A high score means observable evidence is consistent with an intent hypothesis; it does not mean private intent is known.
