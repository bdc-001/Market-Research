"""
Build a multi-event Discovery Council sample.

Frozen architecture: Discovery → evidence expansion → Council → predictions → pending outcomes.
Does not teach agents. Does not write lessons. Skips CHAVDA (episode #1 is not a rule).
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from agents.candidate_expansion import expand_sample_cards
from agents.discovery_config import load_discovery_config
from agents.episode_store import fetch_council_event_ids
from agents.sample_builder import CHAVDA_TICKER, pick_sample_cards, type_counts
from discovery_council import DiscoveryCouncil
from discovery_orchestrator import DiscoveryOrchestrator

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def sample_config(lookback_days: int, max_events_to_llm: int) -> dict:
    cfg = copy.deepcopy(load_discovery_config())
    radar = cfg.setdefault("radar", {})
    radar["announcement_lookback_days"] = int(lookback_days)
    radar["max_events_to_llm"] = int(max_events_to_llm)
    from agents.host_limits import constrained_host
    if constrained_host():
        radar["max_raw_announcements"] = min(int(radar.get("max_raw_announcements") or 500), 120)
        radar["max_events_to_llm"] = min(int(max_events_to_llm), 8)
    return cfg


def run_sample(
    *,
    lookback_days: int = 7,
    max_events_to_llm: int = 50,
    max_n: int = 6,
    max_per_type: int = 1,
    allow_discarded: bool = True,
    skip_discovery: bool = False,
    cards: list[dict] | None = None,
    progress=None,
) -> dict:
    update = progress or (lambda m: print(m, flush=True))
    discovery = None
    if cards is None and not skip_discovery:
        update(f"Discovery sample run lookback={lookback_days}d (config file not rewritten)")
        discovery = DiscoveryOrchestrator().run(
            progress_callback=update,
            cfg=sample_config(lookback_days, max_events_to_llm),
        )
        cards = discovery.get("cards") or []
    cards = cards or []
    already = fetch_council_event_ids()
    picked = pick_sample_cards(
        cards,
        skip_event_ids=already,
        max_n=max_n,
        max_per_type=max_per_type,
        allow_discarded=allow_discarded,
    )
    update(
        f"Sample pick: {len(picked)} cards, types={type_counts(picked)} "
        f"(skipped {CHAVDA_TICKER} and {len(already)} existing event_ids)"
    )
    packs = expand_sample_cards(picked, progress=update)
    council = DiscoveryCouncil()
    results = []
    for pack in packs:
        ticker = pack.get("ticker")
        path = pack.get("report_path")
        event = pack.get("event") or {}
        if str(ticker or "").upper() == CHAVDA_TICKER:
            update("Skip CHAVDA — episode #1 is not a lesson")
            continue
        update(f"Council: {ticker} type={event.get('event_type')} pack={path}")
        try:
            result = council.run(ticker=ticker, pack_path=path, progress_callback=update)
            result["event_type"] = event.get("event_type")
            result["expansion_path"] = path
            results.append(result)
            update(
                f"Stored {ticker} episode={result.get('episode_id')} "
                f"decision={result.get('decision')}"
            )
        except Exception as exc:
            update(f"Council failed for {ticker}: {exc}")
            results.append({
                "ticker": ticker,
                "error": str(exc),
                "event_type": event.get("event_type"),
                "expansion_path": path,
            })
    inventory = write_inventory(cards, picked, packs, results, discovery)
    return {
        "discovery_report": (discovery or {}).get("report_path"),
        "picked": [
            {
                "ticker": c.get("ticker"),
                "event_type": c.get("event_type"),
                "stage": c.get("stage"),
                "event_id": c.get("event_id"),
            }
            for c in picked
        ],
        "results": results,
        "inventory_path": str(inventory),
        "radar_types": type_counts(cards),
        "sample_types": type_counts(picked),
    }


def write_inventory(cards, picked, packs, results, discovery) -> Path:
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = REPORTS / f"discovery_sample_{stamp}.md"
    council_ok = [r for r in results if r.get("episode_id")]
    lines = [
        "# Discovery sample inventory",
        "",
        "Phase 2A sample generation. Agents are not taught. Lessons are not written.",
        "CHAVDA is excluded from this batch — one episode is not a general rule.",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Discovery report: {(discovery or {}).get('report_path') or '(reused cards)'}",
        "",
        "## Radar event types (this Discovery run)",
        "",
    ]
    radar = Counter(c.get("event_type") or "unclassified" for c in cards)
    for key, n in sorted(radar.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- `{key}`: {n}")
    lines += ["", "## Council sample (CHAVDA skipped)", ""]
    lines.append("| Ticker | Event type | Stage | Episode | Decision | Pack |")
    lines.append("|---|---|---|---|---|---|")
    pack_by_ticker = {p.get("ticker"): p for p in packs}
    pick_by_ticker = {c.get("ticker"): c for c in picked}
    for row in results:
        ticker = row.get("ticker")
        card = pick_by_ticker.get(ticker) or {}
        pack = pack_by_ticker.get(ticker) or {}
        lines.append(
            "| {ticker} | `{etype}` | {stage} | `{eid}` | {dec} | {pack} |".format(
                ticker=ticker,
                etype=row.get("event_type") or card.get("event_type") or "",
                stage=card.get("stage") or "",
                eid=row.get("episode_id") or row.get("error") or "",
                dec=row.get("decision") or "failed",
                pack=Path(str(row.get("expansion_path") or pack.get("report_path") or "")).name,
            )
        )
    lines += [
        "",
        f"Council episodes written this batch: **{len(council_ok)}**",
        "",
        "Next: wait for horizons. Do not classify failures until several episodes have elapsed.",
        "Do not promote CHAVDA into `lessons`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate Discovery Council episodes (no learning)")
    parser.add_argument("--lookback", type=int, default=7, help="radar lookback days (does not rewrite discovery.yaml)")
    parser.add_argument("--max-llm", type=int, default=50)
    parser.add_argument("--max-n", type=int, default=6, help="max Council episodes this batch")
    parser.add_argument("--max-per-type", type=int, default=1)
    parser.add_argument("--no-discarded", action="store_true")
    args = parser.parse_args()
    result = run_sample(
        lookback_days=args.lookback,
        max_events_to_llm=args.max_llm,
        max_n=args.max_n,
        max_per_type=args.max_per_type,
        allow_discarded=not args.no_discarded,
    )
    print("INVENTORY", result.get("inventory_path"), flush=True)
    print("RADAR_TYPES", json.dumps(result.get("radar_types"), default=str), flush=True)
    print("SAMPLE_TYPES", json.dumps(result.get("sample_types"), default=str), flush=True)
    print("EPISODES", len([r for r in result.get("results") or [] if r.get("episode_id")]), flush=True)


if __name__ == "__main__":
    main()
