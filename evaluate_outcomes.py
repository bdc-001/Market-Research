"""
Phase 2A CLI — evaluate stored Council episodes against later prices.

Does not change Council, Discovery, or QuanTum. Does not write lessons.
"""
from __future__ import annotations

import argparse
from datetime import datetime

from agents.outcome_evaluator import (
    evaluate_chavda,
    evaluate_episode,
    write_outcome_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2A episode outcome evaluator")
    parser.add_argument("--episode", default="", help="episode_id to evaluate")
    parser.add_argument("--chavda", action="store_true", help="seed and evaluate CHAVDA episode #1")
    parser.add_argument("--as-of", dest="as_of", default="", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--no-fetch", action="store_true", help="do not download prices")
    args = parser.parse_args()

    as_of = None
    if args.as_of:
        as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()

    if args.episode:
        result = evaluate_episode(args.episode, as_of=as_of, fetch_prices=not args.no_fetch)
    else:
        result = evaluate_chavda(as_of=as_of, fetch_prices=not args.no_fetch)

    path = write_outcome_report(result)
    pending = sum(1 for h in result["horizons"] if h.get("status") == "pending")
    print(f"episode {result['episode_id']}", flush=True)
    print(f"ticker {result['ticker']} entry {result.get('entry_date')} {result.get('entry_price')}", flush=True)
    print(f"horizons pending={pending}/{len(result['horizons'])}", flush=True)
    print(f"report {path}", flush=True)


if __name__ == "__main__":
    main()
