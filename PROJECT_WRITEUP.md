# Financial Intelligence & QuanTum Engine — Project Write-Up

**What we're building:** An AI-powered financial intelligence system that discovers stock opportunities from **live news**, confirms them with **technical analysis**, and delivers ranked picks and PDF reports via **Telegram** — without relying on a hardcoded stock list for short-term ideas.

---

## Vision

Instead of scanning a fixed list of 80–100 stocks every day, we let **the market tell us what to look at**. Headlines from Indian financial news (earnings, policy, sector moves, block deals) drive which names enter the pipeline. We then fetch price and technical data only for those names, score them on **news catalyst strength** and **technical confirmation**, and produce a clear, data-backed report. For longer horizons (1 year, 5 years), we still run a systematic multi-factor model across a broader NSE universe.

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                  TELEGRAM BOT (@WarrenDalioBot)          │
                    │  /picks  /news  /stock  /sector  /reports  /emerging…   │
                    └─────────────────────────────────────────────────────────┘
                                                │
                    ┌───────────────────────────┴───────────────────────────┐
                    │              QuanTum Engine Orchestrator (v3)          │
                    └───────────────────────────┬───────────────────────────┘
                                                │
        ┌───────────────────────────────────────┼───────────────────────────────────────┐
        │                                       │                                       │
        ▼                                       ▼                                       ▼
┌───────────────┐                    ┌───────────────────┐                    ┌───────────────┐
│ NEWS SCANNER  │                    │ DATA COLLECTOR   │                    │ FACTOR SCORER │
│ (Phase 1)     │ ── tickers ──►    │ (Phase 2)        │ ── DataFrame ──►   │ (Phase 3)     │
│               │                    │                  │                    │               │
│ • RSS feeds   │                    │ • yfinance       │                    │ • Weekly:     │
│ • Gemini      │                    │ • Price, volume  │                    │   news + tech │
│ • Ticker +    │                    │ • RSI, MACD,     │                    │   + momentum  │
│   catalyst    │                    │   SMAs, returns  │                    │ • Year/5Y:    │
│   extraction  │                    │ • Fundamentals   │                    │   value, qual, │
│               │                    │                  │                    │   sector grow │
└───────────────┘                    └───────────────────┘                    └───────┬───────┘
        │                                       │                                       │
        │                                       │                                       │
        └───────────────────────────────────────┼───────────────────────────────────────┘
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │ QUANTUM SYNTHESIZER   │
                                    │ • Methodology         │
                                    │ • Weekly: catalyst +  │
                                    │   technical text      │
                                    │ • Annual/5Y: tables   │
                                    │ • Risk & disclaimer   │
                                    └───────────┬───────────┘
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │ REPORT → PDF          │
                                    │ (report_to_pdf.py)    │
                                    │ Styled, table-safe    │
                                    └───────────┬───────────┘
                                                │
                                                ▼
                                    Reports saved + sent to Telegram
```

---

## Core Components

### 1. News Scanner (News-First Discovery)

- **Role:** Decide *which* stocks are in play this week — no hardcoded universe.
- **Inputs:** RSS feeds from Economic Times, Moneycontrol, Business Standard, Mint, NDTV Profit (and optional ET Stocks / MC Market Outlook).
- **Process:** Headlines are sent to **Gemini**, which extracts:
  - **NSE ticker symbols** mentioned or impacted (sector news, policy, earnings, block deals, upgrades/downgrades).
  - **Catalyst:** 1–2 sentence description of the specific news.
  - **Sentiment:** -1 (bearish) to +1 (bullish).
  - **Urgency:** high / medium / low (for weighting).
- **Output:** List of 20–50 stocks with catalyst and sentiment — this becomes the **weekly universe**.

### 2. Data Collector

- **Role:** Fetch price, volume, technicals, and fundamentals only for the stocks we care about.
- **Source:** yfinance (NSE: `TICKER.NS`).
- **Computed:** RSI, MACD, SMAs (20/50/200), 1m/3m/6m/12m returns, 20-day annualized volatility, volume ratio; plus P/E, P/B, ROE, D/E, profit margin, earnings yield, market cap.
- **Storage:** SQLite (`stock_data_v2`, `signal_log`) for history and accuracy tracking.
- **Weekly path:** Fetches **news-discovered tickers** (fast, focused).  
- **Annual/5-Year path:** Fetches **full NSE universe** (80+ names) for systematic screening.

### 3. Factor Scorer (Multi-Horizon)

**Weekly (1–7 days) — news-driven**

- **Factors:** News Catalyst (25%), Technical (35%), Momentum (30%), Volatility (10%).
- **News Catalyst:** Gemini sentiment + urgency, mapped to a 0–100 score; stocks not in news get a lower baseline so they rank below news-driven names.
- **Technical:** RSI zone (Gaussian around 50), MACD vs signal, trend (price vs 50/200 SMA).
- **Momentum:** Weighted 1m / 3m / 6m returns.
- **Conviction:** Count of factors (news, technical, momentum) in top 20% → Very High / High / Moderate / Low.

**Annual (6–12 months) & 5-Year (structural)**

- **Factors:** Value, Quality, Momentum, Technical, Volatility, **Sector Growth**.
- **Value:** Earnings yield + inverse P/B.
- **Quality:** ROE + leverage + margin, with **sector correction for financials** (Banks/NBFCs get neutral D/E and margin; ROE drives their quality score).
- **Sector Growth:** Structural outlook by industry (e.g. Defence, Green Energy, Digital, CapGoods, Pharma) to reduce BFSI bias and reward “bright future” sectors.
- **Conviction:** 5 core factors in top 20% → Very High down to None.

### 4. Synthesizer (Report Generator)

- **Deterministic:** No LLM narrative; all text is code-generated from scores and metadata.
- **Weekly section:** For each top pick, a short paragraph: **Catalyst** (why it’s in the news), then price vs SMAs, RSI, MACD, momentum, volume, volatility.
- **Annual/5-Year sections:** Compact rankings table, factor breakdown table, and short stock profiles (price, P/E, ROE, returns, sector score) with a one-line factor interpretation.
- **Also includes:** Methodology, horizon weights, conviction levels, optional backtest summary, signal-accuracy stats, risk metrics, disclaimer.

### 5. Report → PDF

- **Input:** Markdown report from the synthesizer.
- **Process:** `markdown` → HTML, then `xhtml2pdf` with custom CSS (tables, fonts, spacing) so tables don’t distort in the PDF.
- **Output:** Styled PDF attached in Telegram and saved under `reports/`.

### 6. Telegram Bot

- **Commands:** `/picks` (QuanTum report), `/news` (headlines + sentiment), `/stock TICKER`, `/sector NAME`, `/toppicks`, `/emerging`, `/developed`, `/reports`.
- **/picks flow:** Runs the full QuanTum pipeline (news scan → data → scoring → report → PDF), sends a short summary plus the PDF.
- **Security:** Optional allowlist of chat IDs; bot token via environment or config.

---

## Data Flow Summary

| Step | Weekly Path | Annual / 5-Year Path |
|------|-------------|----------------------|
| 1 | Scan RSS → Gemini → list of tickers + catalysts | — |
| 2 | Fetch data for **news tickers** (+ full universe for long-term) | Fetch data for **full NIFTY universe** |
| 3 | Score with **news_catalyst + technical + momentum** | Score with **value, quality, momentum, technical, vol, sector_growth** |
| 4 | Report: catalyst-led paragraphs | Report: factor tables + profiles |
| 5 | PDF → Telegram + `reports/` | Same |

---

## Tech Stack

- **Language:** Python 3 (ESM-style scripts where needed).
- **Data:** yfinance, pandas, numpy.
- **LLM:** Google Gemini (ticker/catalyst extraction, sentiment).
- **Storage:** SQLite (signals, optional history).
- **PDF:** markdown → HTML (markdown lib), HTML → PDF (xhtml2pdf).
- **Delivery:** Telegram Bot API (python-telegram-bot), optional requests for one-shot send.

---

## What Makes This Different

1. **No hardcoded weekly universe**  
   Short-term ideas come from **who is in the news**, not a fixed list. New names (e.g. NETWEB, GOKEX, sector beneficiaries) appear automatically when headlines mention them.

2. **Catalyst-first storytelling**  
   Each weekly pick leads with *why* it’s in play (earnings, tariff ruling, demerger, crude move, etc.), then technicals confirm.

3. **Dual regime**  
   **Weekly = news + technicals + momentum.** **Annual/5-Year = fundamentals + sector growth + same factors**, so long-term picks stay systematic and sector-aware.

4. **Reproducible, auditable**  
   Methodology and weights are documented in the report; scoring is deterministic; signals are logged for later accuracy checks.

5. **One pipeline, one report**  
   One run produces both “what’s moving this week” and “best names for the year / next 5 years” in a single PDF.

---

## Current Status

- **News Scanner:** Live; discovers 30–50 tickers per run from 7 RSS feeds.
- **Data Collector:** Fetches 2 years of daily data, computes all factor inputs, writes to SQLite.
- **Factor Scorer:** v4 with news_catalyst for weekly; sector-aware value/quality and sector growth for long-term.
- **Synthesizer:** v3; weekly = catalyst + technical text; annual/5Y = tables + profiles.
- **PDF:** Styled conversion; tables tuned to avoid distortion.
- **Telegram Bot:** `/picks` runs full pipeline and sends PDF; other commands (news, stock, sector, reports) wired.
- **Orchestrator:** News-first weekly + systematic annual/5-year in one `QuantumEngineOrchestrator().run()`.

---

## Possible Next Steps

- **Earnings calendar:** Filter or boost catalysts around result dates.
- **More feeds:** Add sector-specific or global RSS for broader coverage.
- **Backtest automation:** Run walk-forward backtest on a schedule and include summary in report.
- **Alerts:** Notify when a high-conviction weekly pick appears (e.g. 3/3 factors in top 20%).
- **Position sizing:** Optional Kelly or risk-parity overlay using volatility from the scorer.

---

## Repository Context

This project lives under **OpenClaw** (`Stock Research/Market Research/`). It uses:

- **OpenClaw** for gateway/channels/cron if you want scheduled runs and multi-channel delivery.
- **Standalone scripts** (e.g. `quantum_orchestrator.py`, `telegram_bot.py`) so you can also run QuanTum and the bot without the full OpenClaw stack.

The write-up above describes the **Financial Intelligence / QuanTum Engine** we are building: news-first discovery, technical confirmation, multi-horizon factor scoring, and PDF reports delivered via Telegram.
