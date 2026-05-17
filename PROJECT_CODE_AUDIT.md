# Project Code Audit

Audit date: 2026-05-17

This project now has one primary production path:

`main.py` -> `financial_system.cli` -> `financial_system.pipeline` -> Google Sheet state/export.

Cloud execution is handled by the Cloud Run Job workflow in `.github/workflows/deploy-cloud-run.yml`.

## Production Entry Points

| Path | Necessity | Notes |
| --- | --- | --- |
| `main.py` | Required | Thin CLI entry point for local and container execution. |
| `Dockerfile` | Required | Builds the Cloud Run Job image and runs `python -m financial_system.cli run`. |
| `.github/workflows/deploy-cloud-run.yml` | Required | Builds/pushes image, deploys Cloud Run Job, and ensures daily schedulers at 08:30, 11:00, 14:00 Asia/Taipei. |
| `requirements.txt` | Required | Local CLI dependencies. |
| `requirements-cloud.txt` | Required | Cloud Run dependencies including Google auth/API clients. |
| `.env.example` | Required | Local runtime configuration template. |
| `.dockerignore` | Required | Keeps generated data, logs, virtualenvs, and docs out of container builds. |
| `.gitignore` | Required | Keeps secrets, local DB files, generated reports, logs, and caches out of git. |

## Core Runtime Modules

| Path | Necessity | Notes |
| --- | --- | --- |
| `financial_system/cli.py` | Required | Defines supported commands: daily run, symbols, keyword inspection, risk, and monitor events. |
| `financial_system/pipeline.py` | Required | Main daily report orchestration. Now validates Google credentials before sheet-backed runs. |
| `financial_system/config.py` | Required | Central settings loader and config file paths. Includes `GOOGLE_SHEET_STATE_BACKEND`. |
| `financial_system/google_auth.py` | Required | Refreshes Google ADC credentials before Sheet access. Local fallback opens `gcloud auth application-default login`. |
| `financial_system/google_sheet_database.py` | Required | Sheet-backed state store for reports, keyword trends, keyword weights, and monitor events. |
| `financial_system/google_sheet_exporter.py` | Required | Writes the daily report artifacts to Google Sheets. Uses the shared auth refresh helper. |
| `financial_system/google_sheet_bridge.py` | Required | Imports monitor events from a sheet CSV URL. |
| `financial_system/database.py` | Required compatibility layer | Keeps the old function API but routes to Google Sheets when enabled. SQLite remains only as fallback if Sheet backend is disabled. |
| `financial_system/storage.py` | Required | Uploads report markdown to GCS. DB backup/restore is disabled when Google Sheet state is active. |
| `financial_system/dates.py` | Required | Stable report dates and run IDs. |
| `financial_system/notes.py` | Required | Reads manual daily note files. |
| `financial_system/market.py` | Required | Fetches market snapshots and writes local JSON artifacts. |
| `financial_system/news.py` | Required | Collects RSS/Google News items and writes local JSON artifacts. |
| `financial_system/keywords.py` | Required | Builds and ranks news/search keywords. |
| `financial_system/dynamic_weights.py` | Required | Builds condition-sensitive search queries from market state. |
| `financial_system/anomaly.py` | Required | Ranks biggest market movers and anomaly search queries. |
| `financial_system/trend_monitor.py` | Required | Evaluates configured long-term trend monitors. |
| `financial_system/correlation.py` | Required | Computes cross-market correlation context. |
| `financial_system/risk_analyzer.py` | Required | Calculates risk metrics for report context. |
| `financial_system/monitor_bridge.py` | Required | Defines external monitor event model and formatting. |
| `financial_system/report.py` | Required | Renders markdown reports. |
| `financial_system/llm.py` | Required | Builds AI report content when `OPENAI_API_KEY` is configured. |
| `financial_system/__init__.py` | Required | Package marker and version. |

## Optional Or Legacy Runtime Modules

| Path | Necessity | Notes |
| --- | --- | --- |
| `financial_system/web.py` | Optional | Flask HTTP wrapper for service-style execution. Current production path uses Cloud Run Jobs, not this web server. |
| `financial_system/main.py` | Optional legacy | Async trading-system orchestrator, separate from the daily CLI pipeline. Retained for experiments/tests. |
| `financial_system/automated_trader.py` | Optional legacy | Paper/signal trading workflow used by older monitor tests, not production daily report execution. |
| `financial_system/realtime_monitor.py` | Optional legacy | Real-time monitor prototype. Current production report imports monitor events from Google Sheets instead. |
| `financial_system/trend_predictor.py` | Optional legacy | Trend prediction prototype used by older orchestrator/tests, not the daily report path. |
| `financial_system/db_cloud.py` | Optional legacy | Cloud SQL/Postgres helper. Current production state backend is Google Sheets. |

## Configuration Files

| Path | Necessity | Notes |
| --- | --- | --- |
| `config/symbols.json` | Required | Market universe for daily snapshots. |
| `config/policy_keywords.json` | Required | Policy/company query expansion. |
| `config/keyword_weights.json` | Required seed config | Static keyword weights used by keyword ranking. |
| `config/trend_keywords.json` | Required config | Long-term theme keyword groups. |
| `config/trend_monitors.json` | Required config | Long-term trend monitor thresholds. |
| `config/correlation_pairs.json` | Required config | Cross-market correlation pairs. |
| `config/news_sources.json` | Required config | Additional RSS/news sources. |
| `config/daily_tracking_keywords.json` | Required config | Daily keyword seed list and search queries. |
| `config/settings.json` | Optional legacy config | Not imported by the current CLI pipeline, retained as historical config. |
| `config/.env.example` | Optional helper | Secondary env template. Main template is root `.env.example`. |

## Apps Script And Sheet Sync

| Path | Necessity | Notes |
| --- | --- | --- |
| `google_apps_script/realtime_monitor_trader.gs` | Required integration artifact | Apps Script monitor writer for Google Sheet events. |
| `google_apps_script/simple_test.gs` | Optional | Apps Script smoke test. |
| `google_apps_script/appsscript.json` | Required for Apps Script | Project manifest. |
| `google_apps_script/README.md` | Required docs | Apps Script setup notes. |
| `gas_sync/google_sheets_sync.py` | Optional helper | Standalone Google Sheets sync utility. |
| `gas_sync/gas_sync_service.py` | Optional helper | Sync service helper. |
| `gas_sync/setup_sheets.py` | Optional helper | One-time sheet setup helper. |
| `gas_sync/README.md` | Required docs if using `gas_sync` | Setup notes. |

## Development And Deployment Helpers

| Path | Necessity | Notes |
| --- | --- | --- |
| `deploy_cloud_run.py` | Optional legacy deploy helper | Service-oriented deploy script. Primary deployment is GitHub Actions Cloud Run Job workflow. |
| `deploy.ps1` | Optional legacy deploy helper | PowerShell deployment helper. Primary deployment is GitHub Actions. |
| `local_dev.py` | Optional dev helper | Runs local or Docker Cloud Run simulation. |
| `setup-cloudsql.sh` | Optional legacy helper | Cloud SQL setup script. Not needed for Google Sheet state backend. |
| `setup-vscode-cloud-run.ps1` | Optional dev helper | VS Code Cloud Run task setup. |
| `setup_github.py` | Optional setup helper | GitHub setup automation. |
| `VS_CODE_CLOUD_RUN_README.md` | Optional docs | VS Code/Cloud Run developer setup. |
| `README_ADVANCED.md` | Optional docs | Advanced setup notes. |

## Root Legacy Scripts

| Path | Necessity | Notes |
| --- | --- | --- |
| `ai_analyzer.py` | Legacy | Early standalone analyzer; not imported by current daily pipeline. |
| `api_integration.py` | Legacy | Early standalone integration layer; not imported by current daily pipeline. |
| `core_data_manager.py` | Legacy | Early standalone data manager; not imported by current daily pipeline. |
| `launch.py` | Legacy launcher | Early launcher; not part of Cloud Run Job path. |
| `test_system.py` | Optional legacy smoke tests | Exercises older trading/monitor modules. Keep as reference until replaced with pytest coverage. |
| `video_cover.py` | Optional media helper | Generates project media, not runtime code. |
| `vidoe_cover.png` | Optional media asset | Existing generated visual asset; filename typo is historical. |

## Removed Or Excluded

| Path | Decision | Notes |
| --- | --- | --- |
| `decision_intent_analysis/` | Detached workspace | Split away from the daily financial report runtime. The Taiwan stock valuation SQLite workflow now lives here for future separate development. |
| `financial_system/taiwan_stock_valuation.py` | Removed from main package | Moved to `decision_intent_analysis/taiwan_stock_valuation.py`; no longer imported by the production CLI. |
| `README_TAIWAN_STOCK_VALUATION.md` | Removed from root docs | Moved to `decision_intent_analysis/README_TAIWAN_STOCK_VALUATION.md`. |
| `cloudbuild.yaml` | Not primary | Existing file targets an older Cloud Build/GKE-style flow and references infrastructure not used by the current Cloud Run Job workflow. Do not use unless rewritten. |
| `node.msi` | Excluded | Local installer artifact, ignored by git. |
| `.env`, `.env.cloud` | Excluded | Local/secret environment files. |
| `data/*.db`, generated JSON, `outputs/*.md`, `logs/` | Excluded | Runtime artifacts, not source code. |

## Current Cleanup Position

- The production daily report path is coherent and centered on Google Sheets.
- SQLite is still present in code as a fallback compatibility layer only. It is not used by the Cloud Run daily report path when `GOOGLE_SHEET_STATE_BACKEND=true`.
- The root legacy scripts are not deleted in this cleanup because they are tracked historical tools and removing them would be a larger product decision. Their non-production status is now documented here.
- The Taiwan stock valuation SQLite workflow is no longer part of this project package or CLI; continue it inside `decision_intent_analysis/`.
- Future cleanup can remove or archive `financial_system/main.py`, `automated_trader.py`, `realtime_monitor.py`, `trend_predictor.py`, and root legacy scripts once the user confirms those experimental workflows are no longer needed.
