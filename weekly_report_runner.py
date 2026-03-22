"""
Weekly Report Runner
====================
Invoked every Monday morning by the OpenClaw cron job.
Runs all three financial pipelines in sequence:
  1. QuanTum Engine (multi-horizon stock picks)
  2. Sector Reports (Defence, Healthcare, Green Energy)
  3. Buffett-Dalio Screener (SME quality screen)

Prints a concise summary to stdout — OpenClaw reads this and
delivers it to WhatsApp + Telegram via the cron announce mechanism.

Usage:
  py weekly_report_runner.py
  py weekly_report_runner.py --quantum-only
  py weekly_report_runner.py --sectors-only
"""

import os
import sys
import time
import argparse
from datetime import datetime

# Fix Windows console encoding so emojis don't crash
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Make sure we run from the financial-assistant directory ───────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

REPORTS_DIR = os.path.join(SCRIPT_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

WEEK_LABEL = datetime.now().strftime("Week of %d %b %Y")
TIMESTAMP  = datetime.now().strftime("%Y%m%d_%H%M")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 1: QuanTum Engine
# ─────────────────────────────────────────────────────────────────────────────
def run_quantum() -> dict:
    """
    Run the full QuanTum Engine pipeline.
    Returns a summary dict with picks and report path.
    """
    section("Pipeline 1/3: QuanTum Engine")

    try:
        from quantum_orchestrator import QuantumEngineOrchestrator

        steps = []
        def log(msg):
            steps.append(msg)
            print(f"  {msg}")

        engine = QuantumEngineOrchestrator()
        result = engine.run(progress_callback=log)

        if "error" in result:
            return {"status": "error", "detail": result["error"]}

        # Format compact picks summary
        def fmt_picks(df, label):
            lines = [f"\n*{label}*"]
            for i, (_, r) in enumerate(df.head(5).iterrows(), 1):
                lines.append(f"  {i}. {r['ticker']} — Score: {r['final_score']}")
            return "\n".join(lines)

        summary = (
            fmt_picks(result["week_picks"],     "This Week (Breakout)")
            + fmt_picks(result["year_picks"],   "This Year (Swing)")
            + fmt_picks(result["fiveyear_picks"], "5 Years (Compounders)")
        )

        return {
            "status": "ok",
            "summary": summary,
            "report_path": result.get("report_path", ""),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 2: Sector Reports
# ─────────────────────────────────────────────────────────────────────────────
WEEKLY_SECTORS = [
    "Indian Defence & Aerospace",
    "Indian Healthcare & Diagnostics",
    "Indian Green Energy & Renewables",
]

def run_sector_reports() -> list[dict]:
    """
    Run sector analysis for WEEKLY_SECTORS.
    Returns list of result dicts.
    """
    section("Pipeline 2/3: Sector Reports")

    results = []
    try:
        from sector_orchestrator import SectorOrchestrator
        orch = SectorOrchestrator()

        for sector in WEEKLY_SECTORS:
            print(f"\n  Analyzing: {sector}")
            try:
                report = orch.run_sector_analysis(sector)

                path = os.path.join(
                    REPORTS_DIR,
                    f"Sector_{sector.replace(' ', '_').replace('&', 'and')}_{TIMESTAMP}.md"
                )
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# Sector Report: {sector}\n")
                    f.write(f"*Generated: {datetime.now().strftime('%d %b %Y %H:%M')} IST*\n\n")
                    f.write(report)

                results.append({"sector": sector, "status": "ok", "path": path})
                print(f"  Saved: {os.path.basename(path)}")
                time.sleep(2)  # be gentle with Gemini rate limits

            except Exception as e:
                print(f"  ERROR in {sector}: {e}")
                results.append({"sector": sector, "status": "error", "detail": str(e)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append({"sector": "ALL", "status": "error", "detail": str(e)})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline 3: Buffett-Dalio Screener
# ─────────────────────────────────────────────────────────────────────────────
SCREENER_INDUSTRIES = [
    "Indian Defence SMEs",
    "Indian Healthcare & Diagnostics",
]

def run_buffett_dalio() -> dict:
    """
    Run the Buffett-Dalio pipeline for configured industries.
    """
    section("Pipeline 3/3: Buffett-Dalio Screener")

    paths = []
    errors = []

    try:
        import batch_pipeline as bp

        for industry in SCREENER_INDUSTRIES:
            print(f"\n  Screening: {industry}")
            try:
                bp.run_pipeline(industry)
                # batch_pipeline saves its own file under reports/
                paths.append(industry)
            except Exception as e:
                print(f"  ERROR in {industry}: {e}")
                errors.append(f"{industry}: {e}")
            time.sleep(2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}

    status = "error" if errors and not paths else "ok"
    return {"status": status, "industries": paths, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Weekly Financial Report Runner")
    parser.add_argument("--quantum-only",  action="store_true")
    parser.add_argument("--sectors-only",  action="store_true")
    parser.add_argument("--screener-only", action="store_true")
    parser.add_argument("--no-screener",   action="store_true",
                        help="Skip Buffett-Dalio screener (faster)")
    args = parser.parse_args()

    run_all = not (args.quantum_only or args.sectors_only or args.screener_only)

    print(f"\n{'#'*60}")
    print(f"  WEEKLY FINANCIAL REPORT RUNNER")
    print(f"  {WEEK_LABEL}")
    print(f"{'#'*60}")

    quantum_result  = None
    sector_results  = []
    screener_result = None

    # ── Run selected pipelines ────────────────────────────────────────────────
    if run_all or args.quantum_only:
        quantum_result = run_quantum()

    if run_all or args.sectors_only:
        sector_results = run_sector_reports()

    if (run_all or args.screener_only) and not args.no_screener:
        screener_result = run_buffett_dalio()

    # ── Build the delivery message ────────────────────────────────────────────
    # This is what OpenClaw posts to WhatsApp + Telegram
    lines = [
        f"*Weekly Financial Intelligence Report*",
        f"_{WEEK_LABEL}_",
        "",
    ]

    # QuanTum picks
    if quantum_result:
        if quantum_result["status"] == "ok":
            lines.append("*QUANTUM ENGINE: TOP PICKS*")
            lines.append(quantum_result.get("summary", ""))
            rp = quantum_result.get("report_path", "")
            if rp:
                lines.append(f"\nFull Report: `{os.path.basename(rp)}`")
        else:
            lines.append(f"QuanTum Engine: ERROR — {quantum_result.get('detail', '?')}")
        lines.append("")

    # Sector reports
    if sector_results:
        lines.append("*SECTOR REPORTS GENERATED*")
        for sr in sector_results:
            icon = "OK" if sr["status"] == "ok" else "FAILED"
            lines.append(f"  [{icon}] {sr['sector']}")
        lines.append("")

    # Buffett-Dalio screener
    if screener_result:
        if screener_result["status"] == "ok":
            done = ", ".join(screener_result.get("industries", []))
            lines.append(f"*BUFFETT-DALIO SCREENER*: {done}")
        else:
            lines.append(f"Screener: ERROR — {screener_result.get('detail', '?')}")
        lines.append("")

    lines.append("All reports saved to local `reports/` folder.")
    lines.append("Have a profitable week!")

    delivery_message = "\n".join(lines)

    # ── Print the message (OpenClaw cron reads stdout for announce delivery) ──
    section("DELIVERY MESSAGE (OpenClaw will send this)")
    print(delivery_message)

    # Also save a copy of the summary
    summary_path = os.path.join(REPORTS_DIR, f"WeeklySummary_{TIMESTAMP}.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(delivery_message)
    print(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    main()
