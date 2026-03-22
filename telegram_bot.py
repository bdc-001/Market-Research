"""
Financial Intelligence — Telegram Bot (@WarrenDalioBot)
======================================
ALL features from the Streamlit app, accessible via Telegram commands:

  /start          — Welcome + full command list
  /picks          — QuanTum Engine: AI stock picks (Week / Year / 5Y)
  /news           — High-impact market news with sentiment
  /stock TICKER   — Full 7-agent stock deep-dive (e.g. /stock RELIANCE)
  /sector NAME    — Sector analysis report (e.g. /sector Banking)
  /toppicks       — Top Picks: batch screen + rank Nifty stocks
  /emerging       — Emerging Markets research (India, China, Brazil)
  /developed      — Developed Markets research (USA, EU, Japan)
  /reports        — Browse & download saved reports
  /help           — Full command list

Run: py telegram_bot.py  (from the financial-assistant folder)
"""

import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode
from report_to_pdf import md_to_pdf

# ── Configuration ─────────────────────────────────────────────────────────────
# Set TELEGRAM_BOT_TOKEN in .streamlit/secrets.toml (never hardcode here)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise EnvironmentError(
        "TELEGRAM_BOT_TOKEN not set. Add it to .streamlit/secrets.toml"
    )
# Optional: restrict to your personal chat ID (security)
# Leave empty [] to allow all users.
ALLOWED_CHAT_IDS = []
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_allowed(update: Update) -> bool:
    if not ALLOWED_CHAT_IDS:
        return True
    return update.effective_chat.id in ALLOWED_CHAT_IDS


async def send_long(update: Update, text: str, parse_mode=None):
    """Splits messages > 4000 chars (Telegram limit is 4096)."""
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            await update.message.reply_text(
                chunk,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
        except Exception:
            # Fallback: send without markdown if parse fails
            await update.message.reply_text(
                chunk, disable_web_page_preview=True
            )


async def send_file(update: Update, content: str, filename: str, caption: str):
    """Saves content as Markdown, converts to PDF, and sends both."""
    os.makedirs("reports", exist_ok=True)
    md_path = f"reports/{filename}"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        pdf_path = md_to_pdf(md_path=md_path)
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(
                f, filename=os.path.basename(pdf_path),
                caption=caption
            )
    except Exception as e:
        logger.warning("PDF conversion failed, sending .md instead: %s", e)
        with open(md_path, "rb") as f:
            await update.message.reply_document(
                f, filename=filename, caption=caption
            )

    return md_path


def fmt_picks(df, n=5) -> str:
    """Formats top picks as a Telegram-friendly list with factor data."""
    lines = []
    for i, (_, row) in enumerate(df.head(n).iterrows(), 1):
        ticker = row.get("ticker", "N/A")
        score = row.get("composite_score", row.get("final_score"))
        price = row.get("close")
        conviction = row.get("conviction", "N/A")
        agreement = row.get("factor_agreement", "?")

        s_score = f"{score:.1f}" if isinstance(score, (int, float)) else "N/A"
        s_price = f"Rs.{price:.0f}" if isinstance(price, (int, float)) else "N/A"

        lines.append(
            f"*{i}. {ticker}*  Score: {s_score} | {conviction} ({agreement}/5)\n"
            f"   Price: {s_price}"
        )
    return "\n\n".join(lines)


# ── Command Handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("User %s (%s) sent /start",
                update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(
        "*Financial Intelligence Bot*\n"
        "_@WarrenDalioBot — All 8 features from your Streamlit app_\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*STOCK ANALYSIS*\n"
        "/stock RELIANCE — 7-agent deep-dive\n"
        "/sector Banking — Sector report\n\n"
        "*QUANT ENGINE*\n"
        "/picks — AI picks for Week/Year/5Y\n"
        "/toppicks — Batch screen Nifty stocks\n\n"
        "*GLOBAL MARKETS*\n"
        "/emerging — India, China, Brazil analysis\n"
        "/developed — USA, EU, Japan analysis\n\n"
        "*NEWS & REPORTS*\n"
        "/news — High-impact news + sentiment\n"
        "/reports — Browse & download saved reports\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "_Commands take 1-3 min — AI is working!_",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Full Command List — @WarrenDalioBot*\n\n"
        "*Stock & Sector*\n"
        "/stock TICKER — Full 7-agent stock analysis\n"
        "  Example: /stock TCS, /stock HDFC, /stock INFY\n"
        "/sector NAME — Full sector analysis\n"
        "  Example: /sector Banking, /sector IT, /sector Pharma\n\n"
        "*QuanTum Engine*\n"
        "/picks — Scan 80+ stocks with multi-factor algo\n"
        "  Returns top picks for Week, Year, and 5 Years\n"
        "/toppicks — Screen Nifty stocks, rank top opportunities\n\n"
        "*Global Markets*\n"
        "/emerging — 5-agent Emerging Markets report\n"
        "  Covers: India, China, Brazil\n"
        "/developed — 5-agent Developed Markets report\n"
        "  Covers: USA (S&P 500), EU, Japan\n\n"
        "*News & Library*\n"
        "/news — Latest news from ET, Moneycontrol, Mint\n"
        "  With Bullish/Bearish sentiment scoring\n"
        "/reports — Browse last 10 saved reports\n"
        "  Download any report as a file\n\n"
        "_Tip: All reports are auto-saved to your Report Library!_",
        parse_mode=ParseMode.MARKDOWN
    )


# ── /picks ─────────────────────────────────────────────────────────────────────

async def cmd_picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "*QuanTum Engine v6 — Full Pipeline*\n\n"
        "Running 9-phase pipeline:\n"
        "1. Market Regime (BULL/BEAR/SIDEWAYS)\n"
        "2. News Scanner (deep impact scoring)\n"
        "3. Data Fetch (technicals + fundamentals)\n"
        "4. Institutional Flow (NSE delivery %)\n"
        "5. Earnings Revision (multi-source)\n"
        "6. Factor Scoring (sector-relative, regime-adjusted)\n"
        "7. Portfolio Construction\n"
        "8. Alpha Management (decay + exits)\n"
        "9. Report Generation\n\n"
        "_Takes 5-8 minutes..._",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        from quantum_orchestrator import QuantumEngineOrchestrator
        result = QuantumEngineOrchestrator().run()
        if "error" in result:
            await update.message.reply_text(f"Error: {result['error']}")
            return

        news_count = len(result.get("news_data", []))
        regime = result.get("regime", {}).get("regime", "?")
        date_str = datetime.now().strftime("%d %b %Y")

        # Decay/performance summary
        decay_summary = result.get("decay_summary", {})
        perf = result.get("perf_metrics", {})
        active_pos = decay_summary.get("active_positions", 0)
        exits = sum(1 for d in result.get("decay_results", []) if d.get("should_exit"))

        msg = (
            f"*QuanTum v6 — {date_str}*\n"
            f"Market: *{regime}* regime\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*WEEKLY* ({news_count} stocks from news)\n\n"
            f"{fmt_picks(result['week_picks'])}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "*ANNUAL HORIZON*\n\n"
            f"{fmt_picks(result['year_picks'])}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "*5-YEAR HORIZON*\n\n"
            f"{fmt_picks(result['fiveyear_picks'])}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )

        if active_pos > 0 or exits > 0:
            msg += (
                f"*Alpha Management:* {active_pos} active, {exits} exit signals\n"
            )

        if perf and perf.get("signal_count", 0) > 0:
            msg += (
                f"*Live Performance:* Sharpe {perf.get('sharpe', 0):.2f}, "
                f"Alpha {perf.get('alpha', 0):+.1f}%\n"
            )

        msg += "_Full report with decay + performance in PDF_"
        await send_long(update, msg, parse_mode=ParseMode.MARKDOWN)

        rpath = result.get("report_path")
        if rpath and os.path.exists(rpath):
            try:
                pdf_path = md_to_pdf(md_path=rpath)
                with open(pdf_path, "rb") as f:
                    await update.message.reply_document(
                        f, filename=os.path.basename(pdf_path),
                        caption="QuanTum v6: 9-factor + alpha decay + live performance"
                    )
            except Exception:
                with open(rpath, "rb") as f:
                    await update.message.reply_document(
                        f, filename=os.path.basename(rpath),
                        caption="QuanTum v6 Full Report"
                    )
    except Exception as e:
        logger.exception("cmd_picks failed")
        await update.message.reply_text(f"Error: {str(e)[:300]}")


# ── /toppicks ─────────────────────────────────────────────────────────────────

async def cmd_toppicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    # Parse optional sector argument
    sector = " ".join(context.args).strip() if context.args else None
    sector_msg = f" in *{sector}* sector" if sector else " across all sectors"

    await update.message.reply_text(
        f"*Top Picks Engine — Batch Screening{sector_msg}*\n\n"
        "Running multi-agent screening pipeline:\n"
        "- Screening Nifty 500 stocks\n"
        "- Applying Buffett-Dalio filters\n"
        "- Ranking by quality + value + growth\n\n"
        "_Takes 2-3 minutes..._",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        from orchestrator import AgentOrchestrator
        import json

        with open("sectors.json", "r") as f:
            sectors_data = json.load(f)

        # Use requested sector or pick the first available
        if sector:
            target_sector = sector
            tickers = sectors_data.get(sector, sectors_data.get(
                next((k for k in sectors_data if sector.lower() in k.lower()), 
                     list(sectors_data.keys())[0]), []
            ))
        else:
            target_sector = list(sectors_data.keys())[0]
            tickers = sectors_data[target_sector]

        if not tickers:
            await update.message.reply_text(
                f"No tickers found for sector: {sector}\n"
                f"Available: {', '.join(list(sectors_data.keys())[:8])}"
            )
            return

        orch = AgentOrchestrator()
        all_reports = []
        for ticker in tickers[:5]:  # Top 5 to avoid timeout
            report = orch.run_analysis_pipeline(ticker)
            all_reports.append(f"## {ticker}\n\n{report[:500]}...\n\n---")

        combined = (
            f"# Top Picks — {target_sector}\n"
            f"Generated: {datetime.now().strftime('%d %b %Y %I:%M %p')}\n\n"
        ) + "\n".join(all_reports)

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"TG_TopPicks_{target_sector.replace(' ','_')}_{ts}.md"
        await send_file(update, combined, fname, f"Top Picks: {target_sector}")

        await update.message.reply_text(
            f"*Top Picks for {target_sector} done!*\n\n"
            "Analysed top 5 stocks. Report attached above.\n"
            "_Use /stock TICKER for full individual analysis_",
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.exception("cmd_toppicks failed")
        await update.message.reply_text(f"Error: {str(e)[:300]}")


# ── /emerging ─────────────────────────────────────────────────────────────────

async def cmd_emerging(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    # Optional: user can specify country
    focus = " ".join(context.args).strip() if context.args else "India, China, Brazil"

    await update.message.reply_text(
        "*Emerging Markets Research Pipeline*\n\n"
        "Running 5-agent analysis:\n"
        "1. Market Scout — macro indicators\n"
        "2. Sector Analyst — sector opportunities\n"
        "3. Currency Agent — FX & capital flows\n"
        "4. Flow Tracker — FII/DII movements\n"
        "5. Editor — final synthesis (2500+ words)\n\n"
        f"Focus: *{focus}*\n"
        "_Takes 2-3 minutes..._",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        from global_markets_orchestrator import EmergingMarketsOrchestrator
        orch = EmergingMarketsOrchestrator()
        report = orch.run(focus_countries=focus)

        await send_long(update, report[:3500] + "\n\n_[Full report in file below]_")

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"TG_EmergingMarkets_{ts}.md"
        await send_file(update, report, fname, "Emerging Markets Report (2500+ words)")

    except Exception as e:
        logger.exception("cmd_emerging failed")
        await update.message.reply_text(f"Error: {str(e)[:300]}")


# ── /developed ────────────────────────────────────────────────────────────────

async def cmd_developed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    focus = " ".join(context.args).strip() if context.args else "USA, EU, Japan"

    await update.message.reply_text(
        "*Developed Markets Research Pipeline*\n\n"
        "Running 5-agent analysis:\n"
        "1. Market Scout — macro & GDP data\n"
        "2. Valuation Analyst — PE ratios & spreads\n"
        "3. Central Bank Agent — Fed/ECB/BOJ policy\n"
        "4. Sector Tracker — sector rotation\n"
        "5. Editor — final synthesis (2500+ words)\n\n"
        f"Focus: *{focus}*\n"
        "_Takes 2-3 minutes..._",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        from global_markets_orchestrator import DevelopedMarketsOrchestrator
        orch = DevelopedMarketsOrchestrator()
        report = orch.run(focus_regions=focus)

        await send_long(update, report[:3500] + "\n\n_[Full report in file below]_")

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"TG_DevelopedMarkets_{ts}.md"
        await send_file(update, report, fname, "Developed Markets Report (2500+ words)")

    except Exception as e:
        logger.exception("cmd_developed failed")
        await update.message.reply_text(f"Error: {str(e)[:300]}")


# ── /news ────────────────────────────────────────────────────────────────────

async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    scope = "India" if context.args and "india" in " ".join(context.args).lower() else "global"

    await update.message.reply_text(
        f"*Market News Pulse ({scope.title()})*\n"
        "_Scanning ET, Moneycontrol, Mint, Business Standard..._",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        from news_tracker_orchestrator import NewsTrackerOrchestrator
        news = NewsTrackerOrchestrator().run_analysis(scope=scope)

        date_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
        lines = [f"*Market News — {date_str}*\n━━━━━━━━━━━━━━━━━━━━"]

        high = news.get("high_impact", [])
        if high:
            lines.append("\n*HIGH IMPACT*")
            for item in high[:5]:
                s = item.get("sentiment", "NEUTRAL")
                e = {"BULLISH": "UP", "BEARISH": "DN", "NEUTRAL": "--"}.get(s, "--")
                t = item.get("title", "")[:90]
                summ = item.get("summary", "")[:150]
                src = item.get("source", "")
                lines.append(f"\n[{e}] *{t}*\n_{summ}_\nSource: {src}")

        medium = news.get("medium_impact", [])
        if medium:
            lines.append("\n━━━━━━━━━━━━━━━━━━━━\n*MEDIUM IMPACT*")
            for item in medium[:4]:
                lines.append(f"- {item.get('title','')[:80]}")

        low = news.get("low_impact", [])
        if low:
            lines.append("\n*OTHER NEWS*")
            for item in low[:3]:
                lines.append(f"- {item.get('title','')[:70]}")

        lines.append(
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "_/picks for stock picks | /stock TICKER for analysis_"
        )
        await send_long(update, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.exception("cmd_news failed")
        await update.message.reply_text(f"Error fetching news: {str(e)[:300]}")


# ── /stock ────────────────────────────────────────────────────────────────────

async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /stock RELIANCE\nExamples: /stock TCS, /stock HDFC, /stock INFY"
        )
        return

    ticker = context.args[0].upper().strip()
    await update.message.reply_text(
        f"*Analysing {ticker}...*\n\n"
        "7 AI Agents working:\n"
        "1. Historian — 5yr data research\n"
        "2. Market Scout — latest news\n"
        "3. Quant — financials & ratios\n"
        "4. Bull Agent — buy thesis\n"
        "5. Bear Agent — risk analysis\n"
        "6. Chartist — technical entry\n"
        "7. Editor — final 2500-word memo\n\n"
        "_Takes ~2 minutes..._",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        from orchestrator import AgentOrchestrator
        report = AgentOrchestrator().run_analysis_pipeline(ticker)
        await send_long(update, report[:3500] + "\n\n_[Full report in file below]_")

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"TG_{ticker}_{ts}.md"
        await send_file(update, report, fname, f"Full Analysis: {ticker} (2500+ words)")
    except Exception as e:
        logger.exception("cmd_stock failed")
        await update.message.reply_text(f"Error analysing {ticker}: {str(e)[:300]}")


# ── /sector ───────────────────────────────────────────────────────────────────

async def cmd_sector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /sector Banking\n"
            "Examples: /sector IT, /sector Pharma, /sector Defence, /sector FMCG"
        )
        return

    sector = " ".join(context.args).title()
    await update.message.reply_text(
        f"*Analysing {sector} Sector...*\n"
        "_Multi-agent pipeline... ~2 minutes_",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        from sector_orchestrator import SectorOrchestrator
        report = SectorOrchestrator().run_sector_analysis(sector)
        await send_long(update, report[:3500] + "\n\n_[Full report in file below]_")

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"TG_Sector_{sector.replace(' ','_')}_{ts}.md"
        await send_file(update, report, fname, f"Sector Report: {sector} (2500+ words)")
    except Exception as e:
        logger.exception("cmd_sector failed")
        await update.message.reply_text(f"Error: {str(e)[:300]}")


# ── /reports ──────────────────────────────────────────────────────────────────

async def cmd_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        await update.message.reply_text("No reports saved yet. Run /picks, /stock, or /sector first!")
        return

    all_files = sorted(
        [f for f in os.listdir(reports_dir) if f.endswith(".md")],
        key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)),
        reverse=True
    )

    if not all_files:
        await update.message.reply_text("No reports saved yet.")
        return

    # Show list of last 10 reports
    lines = [
        f"*Report Library — {len(all_files)} total*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "_Sending last 5 reports as files..._\n"
    ]

    for i, fname in enumerate(all_files[:10], 1):
        fpath = os.path.join(reports_dir, fname)
        size_kb = os.path.getsize(fpath) / 1024
        mod = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d %b, %H:%M")

        # Icon by type
        if fname.startswith("Sector_") or fname.startswith("TG_Sector_"):
            icon = "F"
        elif fname.startswith("DeepDive_") or fname.startswith("TG_"):
            icon = "S"
        elif fname.startswith("QuanTum_"):
            icon = "Q"
        elif fname.startswith("Emerging") or fname.startswith("Developed"):
            icon = "G"
        else:
            icon = "R"

        lines.append(f"{i}. [{icon}] {fname[:50]}\n   {size_kb:.0f}KB • {mod}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN
    )

    await update.message.reply_text("Sending 3 most recent reports as PDF...")
    for fname in all_files[:3]:
        fpath = os.path.join(reports_dir, fname)
        try:
            pdf_path = md_to_pdf(md_path=fpath)
            with open(pdf_path, "rb") as f:
                await update.message.reply_document(
                    f, filename=os.path.basename(pdf_path),
                    caption=f"Report: {Path(fname).stem}"
                )
        except Exception:
            try:
                with open(fpath, "rb") as f:
                    await update.message.reply_document(
                        f, filename=fname,
                        caption=f"Report: {fname}"
                    )
            except Exception as e:
                await update.message.reply_text(f"Could not send {fname}: {e}")


# ── Unknown command ───────────────────────────────────────────────────────────

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Unknown command. Use /help to see all commands.\n\n"
        "Quick start: /picks, /news, /stock RELIANCE, /reports"
    )


# ── Bot Setup & Run ───────────────────────────────────────────────────────────

ALL_COMMANDS = [
    BotCommand("picks",    "QuanTum: AI picks for Week/Year/5Y"),
    BotCommand("toppicks", "Batch screen: Top Nifty stock picks"),
    BotCommand("emerging", "Emerging Markets: India/China/Brazil"),
    BotCommand("developed","Developed Markets: USA/EU/Japan"),
    BotCommand("news",     "High-impact news + sentiment"),
    BotCommand("stock",    "Stock deep-dive: /stock RELIANCE"),
    BotCommand("sector",   "Sector analysis: /sector Banking"),
    BotCommand("reports",  "Browse & download saved reports"),
    BotCommand("start",    "Welcome & overview"),
    BotCommand("help",     "Full command list"),
]


def main():
    print()
    print("=" * 58)
    print("  @WarrenDalioBot — Financial Intelligence (Full)")
    print("=" * 58)
    print(f"  Token: {TELEGRAM_BOT_TOKEN[:22]}...")
    print()
    print("  ALL 8 features from Streamlit app:")
    print("  /picks  /toppicks  /emerging  /developed")
    print("  /news   /stock     /sector    /reports")
    print()
    print("  Open Telegram -> @WarrenDalioBot -> /start")
    print("  Press Ctrl+C to stop.")
    print("=" * 58)
    print()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("picks",    cmd_picks))
    app.add_handler(CommandHandler("toppicks", cmd_toppicks))
    app.add_handler(CommandHandler("emerging", cmd_emerging))
    app.add_handler(CommandHandler("developed",cmd_developed))
    app.add_handler(CommandHandler("news",     cmd_news))
    app.add_handler(CommandHandler("stock",    cmd_stock))
    app.add_handler(CommandHandler("sector",   cmd_sector))
    app.add_handler(CommandHandler("reports",  cmd_reports))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    async def on_startup(app):
        await app.bot.set_my_commands(ALL_COMMANDS)
        logger.info("Commands registered in Telegram menu")

    app.post_init = on_startup

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
