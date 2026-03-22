---
name: quantum-weekly-reports
description: >
  Runs the full weekly financial intelligence pipeline — QuanTum Engine
  (multi-horizon stock picks), Sector Reports (Defence, Healthcare, Green Energy),
  and Buffett-Dalio Screener — then delivers a concise summary to WhatsApp and
  Telegram. Triggered automatically every Monday at 09:00 IST by an OpenClaw cron
  job, or on demand when the user sends /quantum or /weekly-report.
---

# Quantum Weekly Reports Skill

## Purpose
Generate and deliver the Weekly Financial Intelligence Report every Monday.

## Entry Point
The main script is located at:
```
C:\Users\HP\OpenClaw\Stock Research\Market Research\weekly_report_runner.py
```

## How to Run

### Full Pipeline (all three engines):
```powershell
cd "C:\Users\HP\OpenClaw\Stock Research\Market Research"
py weekly_report_runner.py
```

### QuanTum Engine only (faster, just stock picks):
```powershell
py weekly_report_runner.py --quantum-only
```

### Sector Reports only:
```powershell
py weekly_report_runner.py --sectors-only
```

### Skip the slower Buffett-Dalio screener:
```powershell
py weekly_report_runner.py --no-screener
```

## What the Script Produces
1. **QuanTum Engine report** — Top 5 picks per horizon (weekly / yearly / 5-year),
   saved to `reports/QuantumReport_<timestamp>.md`
2. **Sector Reports** — One `.md` file per sector in `reports/`
3. **Buffett-Dalio memos** — Full investment memos saved to `reports/`
4. **WeeklySummary_<timestamp>.txt** — A compact WhatsApp/Telegram-friendly
   summary of all results (printed to stdout AND saved to reports/)

## On-Demand Triggers
The user may say any of the following to activate this skill:
- `/quantum`
- `/weekly-report`
- "Run the weekly report"
- "Give me the Monday picks"
- "What are this week's stock picks?"
- "Run the financial pipeline"

When triggered on-demand, run the script and post the stdout output to the
requesting channel.

## Environment Requirements
- Python 3.10+ (`py` command on Windows)
- `GEMINI_API_KEY` must be set in environment (it is in `.streamlit/secrets.toml`)
- Run from `financial-assistant/` directory (the script does `os.chdir` automatically)

## Pre-run Environment Setup
If `GEMINI_API_KEY` is not set in the environment, load it first:
```powershell
$env:GEMINI_API_KEY = (Get-Content "C:\Users\HP\OpenClaw\Stock Research\Market Research\.streamlit\secrets.toml" | Select-String "GEMINI_API_KEY" | ForEach-Object { ($_ -split '"')[1] })
```

## Output Format for Delivery
The script prints a WhatsApp/Telegram-friendly message. When running in OpenClaw
cron (isolated session with announce delivery), this stdout is automatically
delivered to the configured channels.

The message format:
```
*Weekly Financial Intelligence Report*
_Week of DD Mon YYYY_

*QUANTUM ENGINE: TOP PICKS*
[horizons and tickers]

*SECTOR REPORTS GENERATED*
  [OK] Indian Defence & Aerospace
  [OK] Indian Healthcare & Diagnostics
  [OK] Indian Green Energy & Renewables

*BUFFETT-DALIO SCREENER*: [industries screened]

All reports saved to local `reports/` folder.
Have a profitable week!
```

## Chunking Long Messages
WhatsApp and Telegram both have message length limits. If the full report
text exceeds ~4000 characters, chunk it and send in multiple messages. OpenClaw
handles this automatically for announce delivery.

## Error Handling
- If any sub-pipeline fails, the summary still reports results from other pipelines
  and marks the failed one as `[FAILED]`
- The agent should NOT retry automatically if QuanTum Engine fails — market data
  APIs may be rate-limited. Notify the user and allow a manual retry.

## Cron Schedule
This skill is registered as two OpenClaw cron jobs (one per delivery channel):
- **quantum-weekly-whatsapp**: Runs every Monday at 09:00 IST (03:30 UTC)
- **quantum-weekly-telegram**: Runs every Monday at 09:01 IST (03:31 UTC)

Cron expression: `30 3 * * 1` (UTC, Monday only)
