"""Run QuanTum v7 pipeline and send PDF to Telegram."""
import sys
import os
import requests

sys.path.insert(0, ".")

# ── Load credentials from environment (set via .streamlit/secrets.toml) ──────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID             = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
    raise EnvironmentError(
        "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .streamlit/secrets.toml"
    )


def send_telegram_doc(path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(path, "rb") as f:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": caption},
                      files={"document": f})


def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})


def main():
    from quantum_orchestrator import QuantumEngineOrchestrator
    from report_to_pdf import md_to_pdf

    print("Starting QuanTum v7 full pipeline...")
    print("  10-phase institutional-grade system")
    print("  NEW: Entry Timing Engine (execution alpha)")
    print("    - Pullback-to-support scoring")
    print("    - Volume confirmation")
    print("    - Volatility compression breakout")
    print("    - RSI stability filter")
    print()

    result = QuantumEngineOrchestrator().run()

    if "error" in result:
        print(f"ERROR: {result['error']}")
        send_telegram_msg(f"QuanTum v7 Error: {result['error']}")
        return

    rpath = result.get("report_path")
    print(f"\nReport: {rpath}")

    for label, key in [("Week", "week_picks"), ("Year", "year_picks"), ("5Yr", "fiveyear_picks")]:
        df = result.get(key)
        if df is not None and not df.empty:
            cols = ["ticker", "composite_score", "conviction"]
            if "entry_score" in df.columns:
                cols.append("entry_score")
            if "entry_status" in df.columns:
                cols.append("entry_status")
            top3 = df.head(3)[cols]
            print(f"\n{label} top:")
            print(top3.to_string())

    # Entry timing summary
    for label, key in [("Week", "entry_week"), ("Year", "entry_year"), ("5Yr", "entry_fiveyear")]:
        edf = result.get(key)
        if edf is not None and not edf.empty:
            allowed = edf["entry_allowed"].sum()
            total = len(edf)
            avg = edf["entry_score"].mean()
            print(f"\n{label} entry: {allowed}/{total} ready (avg score {avg:.0f})")

    ds = result.get("decay_summary", {})
    print(f"\nDecay: {ds.get('active_positions', 0)} active, {ds.get('total_exited', 0)} exited")

    exits = [d for d in result.get("decay_results", []) if d["should_exit"]]
    if exits:
        print("Exit signals:")
        for e in exits[:5]:
            print(f"  {e['ticker']}: {e['exit_reason']} (P&L: {e['pnl_pct']:+.1f}%)")

    perf = result.get("perf_metrics", {})
    if perf and "error" not in perf:
        print(f"\nPerformance: Sharpe={perf.get('sharpe', 0):.2f}, "
              f"Alpha={perf.get('alpha', 0):+.1f}%, "
              f"Hit={perf.get('hit_rate', 0):.0%}")
    else:
        print(f"Performance: {perf.get('error', 'N/A')}")

    if rpath and os.path.exists(rpath):
        try:
            pdf_path = md_to_pdf(md_path=rpath)
            print(f"PDF: {pdf_path}")
            send_telegram_doc(
                pdf_path,
                "QuanTum v7: 10-phase pipeline + Entry Timing Engine (execution alpha)"
            )
            print("Sent to Telegram!")
        except Exception as e:
            print(f"PDF failed: {e}, sending MD")
            send_telegram_doc(rpath, "QuanTum v7 Report")

    print("\nDone.")


if __name__ == "__main__":
    main()
