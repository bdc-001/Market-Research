# QuanTum — Financial Intelligence

An Indian-market equity research app you trigger from your phone. News decides
which stocks are in play, technicals and fundamentals confirm them, and the
system learns from whether its past picks actually beat the Nifty.

Runs as a Streamlit web app. Hosted in the cloud, so your laptop does not need
to be open.

## What it does

- **News-first discovery.** RSS from Economic Times, Moneycontrol, Business
  Standard, Mint and NDTV Profit, extracted by Gemini into tickers with a
  catalyst, sentiment and event type.
- **Multi-horizon scoring.** Nine factors, weighted by market regime, for three
  horizons: this week, this year, five years.
- **Entry timing and portfolio construction.** Pullback, volume and volatility
  checks; risk-adjusted sizing with sector caps.
- **Reports.** Markdown plus a styled PDF, cached so the app opens instantly.
- **Self-learning.** See below.

## Quick start (local)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Secrets go in `.streamlit/secrets.toml` (never committed):

```toml
GEMINI_API_KEY = "..."
TURSO_URL = "libsql://your-db.turso.io"   # optional
TURSO_TOKEN = "..."                        # optional
```

Without Turso the app falls back to a local SQLite file. In the cloud Turso is
strongly recommended: container disks are wiped on restart, and the database is
where learned weights, learned rules and cached reports live.

## Deploy so it runs without your laptop

Hugging Face Spaces, free CPU tier:

1. Push this folder to its GitHub repo (`bdc-001/Market-Research`).
2. Create a Space: SDK **Streamlit**, hardware **CPU basic**, app file `app.py`,
   linked to that repo.
3. In Space settings, add secrets: `GEMINI_API_KEY`, `TURSO_URL`, `TURSO_TOKEN`.
4. Open the `*.hf.space` URL on your phone and use **Add to Home Screen**.

The Space sleeps when idle and wakes when you open it, so the first load after a
gap takes roughly 30 to 60 seconds. That is the trade for a free always-on URL.

### Run modes

The QuanTum tab opens on the last saved report, so you see something useful
immediately. Two modes are available when you run a fresh analysis:

| Mode | Universe | Use when |
| --- | --- | --- |
| Fast | News-discovered stocks plus a trimmed Nifty universe | Triggering from a phone; finishes in a few minutes |
| Full | Complete 80+ stock universe | You want the widest long-horizon coverage |

Weekly picks are identical in both modes because they always come from the news
scanner. Fast mode only narrows the annual and five-year universe.

## How the system learns

Two kinds of memory, because the two halves of the pipeline learn differently.

**Factor weights (numeric).** Every run logs its picks with all nine factor
scores. `SignalVerifier` later fills in what each pick actually did against the
Nifty. `WeightLearner` measures the rank correlation between each factor and
realised alpha, then shrinks the weights toward what worked. Updates are capped
and require at least 30 verified signals, so a thin sample cannot wreck a model.
See `agents/quantum_learning.py`.

**Rules (semantic).** `GEMINI.md` is prepended to every model call and points at
`memory/learned_rules.md`. After each run the critic agent compares picks with
outcomes and appends at most three imperative rules, such as "Always discount
block-deal headlines to low urgency because the move precedes the story." Rules
are mirrored to the database and restored on boot, so a container restart does
not erase what the system has learned. See `agents/quantum_critic.py`.

## Skills

Skills live in `skills/<name>/SKILL.md` with YAML front matter. Only the front
matter is read at startup; the full instruction body is loaded when a skill is
actually used (`agents/skill_loader.py`).

| Skill | Purpose |
| --- | --- |
| `news_extractor` | Headlines to tickers, catalyst, sentiment, event type |
| `stock_screener` | Buffett-Dalio quality judgement |
| `critic` | Turns outcomes into durable rules |

## Layout

```
app.py                    Streamlit UI
quantum_orchestrator.py   11-phase pipeline
agents/                   scoring, data, flow, learning, critic
skills/                   YAML-front-matter skill definitions
memory/learned_rules.md   accumulated rules
report_store.py           cached reports for instant page loads
weekly_report_runner.py   headless run for a scheduler
telegram_bot.py           optional delivery, not required
```

## Notes

- Screening output is research, not investment advice.
- yfinance and the NSE endpoints rate-limit. A Full run can take several
  minutes; that is the data source, not the app.
