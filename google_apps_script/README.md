# Google Apps Script Monitor

This folder contains the standalone Apps Script monitor/trader signal layer.

Script project:

```text
https://script.google.com/u/0/home/projects/19z2ey5dKhGX68ED8MPfrnLHH7rtBCwgaZNq7Bvnz_nh4v78tSOFn5eIL/edit
```

Google Sheet:

```text
https://docs.google.com/spreadsheets/d/1P5yQwn8K6aN62OTHRTyOlCKxTCedOXWVa8jiSFx87dU/edit
```

## Deploy With Clasp

Install and log in:

```powershell
npm install -g @google/clasp
clasp login
```

Push this folder to the linked Apps Script project:

```powershell
cd google_apps_script
clasp push
```

## First Run

In the Apps Script editor, run:

```text
setupMonitoringSheets
```

Then run:

```text
runMonitoringCycle
```

To schedule automatic execution, run:

```text
createTimeTrigger
```

## Sheet Contract

The Python daily report system reads the `MonitorEvents` tab as CSV and imports rows into SQLite.

Required columns:

```text
id,source,event_type,symbol,severity,event_time,title
```

Optional columns are preserved in the SQLite event payload:

```text
price,previous_close,daily_change_pct,signal,reason,paper_position_size_pct,stop_loss_pct,take_profit_pct
```

Trade output is paper signal context only. This Apps Script does not execute broker orders.
