"""
Discovery Phase A orchestrator.

Universe → corporate radar → Python event filter → liquidity/mcap gates
→ LLM extraction → frozen catalyst+scarcity score → Hidden Catalyst cards
→ observation-only episodes.

Does not call QuanTum. Does not run the Council. Does not write weights.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from agents.agent_trace import TraceLog, trace_to_markdown
from agents.candidate_expansion import expand_candidates
from agents.corporate_event_scanner import news_mention_counts, scan_corporate_events
from agents.discovery_config import frozen_weights, load_discovery_config
from agents.discovery_synthesizer import generate_catalyst_report
from agents.discovery_universe import (
    assign_tiers,
    attach_fundamentals,
    build_opportunity_universe,
    enrich_symbols,
)
from agents.episode_store import write_discovery_episodes
from agents.event_extraction import extract_events
from agents.event_provenance import cluster_events, pick_cluster_heads, stamp_source_ids
from agents.filing_expand import expand_filings
from agents.nse_client import ExchangeClient
from agents.opportunity_scorer import score_opportunities

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


class DiscoveryOrchestrator:
    def run(self, progress_callback=None, cfg=None, step_callback=None) -> dict:
        cfg = cfg or load_discovery_config()
        run_id = str(uuid.uuid4())
        update = progress_callback or (lambda m: print(m, flush=True))
        radar = cfg.get("radar") or {}
        uni_cfg = cfg["universe"]
        client = ExchangeClient(
            cache_ttl_minutes=int(radar.get("cache_ttl_minutes", 180))
        )
        trace = TraceLog("discovery", "Discovery · Phase A.2", on_event=step_callback)

        update("Phase A0 — Opportunity Universe")
        trace.begin("universe")
        universe = build_opportunity_universe(cfg, client=client, progress=update)
        uni_n = 0 if universe is None else len(universe)
        tiers = {}
        if universe is not None and not universe.empty and "tier" in universe.columns:
            tiers = universe["tier"].value_counts().to_dict()
        trace.add(
            step_id="universe",
            name="Universe",
            kind="python",
            receives_from=["NSE SME/Emerge", "Nifty Microcap 250 (if available)"],
            sends_to=["Filings radar"],
            received="Primary tiers: SME + microcap. Liquidity min ADV ₹50 lakh.",
            passed=f"{uni_n} primary names after liquidity. tiers={tiers}",
            parsed={"universe_n": uni_n, "tiers": {str(k): int(v) for k, v in tiers.items()}},
            note="Smallcap is not mixed into primary scores.",
        )

        update("Phase A1 — Corporate Event Scanner")
        trace.begin("radar")
        events = scan_corporate_events(cfg, universe, client=client, progress=update)
        raw_n = len(events)
        type_counts = {}
        for ev in events:
            et = ev.get("event_type") or "unclassified"
            type_counts[et] = type_counts.get(et, 0) + 1
        sample = [
            f"{e.get('ticker')} [{e.get('event_type')}] {(e.get('subject') or '')[:120]}"
            for e in events[:12]
        ]
        trace.add(
            step_id="radar",
            name="Filings radar",
            kind="python",
            receives_from=["Universe", "NSE/BSE announcements", "RSS (secondary)"],
            sends_to=["Liquidity gate"],
            received=f"{uni_n} liquid SME/microcap names",
            passed=(
                f"{raw_n} catalyst-like filings after Python keyword filter.\n"
                f"types={type_counts}\n" + "\n".join(sample)
            ),
            parsed={"raw_events": raw_n, "event_types": type_counts},
            note="No LLM yet. Keyword filter only.",
        )

        tickers = list(dict.fromkeys(e.get("ticker") for e in events if e.get("ticker")))
        update(f"Phase A2 — Liquidity + market-cap hard gate on {len(tickers)} event names")
        trace.begin("gates")
        names = enrich_symbols(tickers, universe, cfg, progress=update)
        allowed = set(names["ticker"].tolist()) if not names.empty else set()
        gated = [e for e in events if e.get("ticker") in allowed]
        update(f"Gated events: {len(gated)} (dropped {raw_n - len(gated)} illiquid/out-of-band)")

        empty_reason = None
        cards: list[dict] = []
        extracted: list[dict] = []
        expansion_packs: list[dict] = []
        if names.empty:
            empty_reason = "No names cleared the liquidity / market-cap hard gates."
        elif not gated:
            empty_reason = "No catalyst-like filings mapped to the liquid SME/microcap universe."

        if not names.empty:
            names = attach_fundamentals(names, progress=update)
            names = assign_tiers(names, uni_cfg)
            primary = set(uni_cfg.get("primary_tiers") or ["sme", "microcap"])
            names = names[names["tier"].isin(primary)].copy()
            allowed = set(names["ticker"].tolist())
            gated = [e for e in gated if e.get("ticker") in allowed]
            update(f"Re-tiered after fundamentals: {len(names)} primary names, {len(gated)} events")

        dropped = raw_n - len(gated)
        trace.add(
            step_id="gates",
            name="Liquidity + mcap gate",
            kind="python",
            receives_from=["Filings radar"],
            sends_to=["PDF filings"],
            received=f"{raw_n} filings on {len(tickers)} tickers",
            passed=(
                f"{len(gated)} events on {len(allowed)} names kept. "
                f"Dropped {dropped} illiquid/out-of-band. {empty_reason or ''}"
            ),
            parsed={"gated_events": len(gated), "names": len(allowed), "dropped": dropped},
            note="Unknown ADV = exclude. No LLM on gated-out names.",
        )

        if gated:
            max_llm = int(radar.get("max_events_to_llm", 40))
            gated = stamp_source_ids(gated)
            update("Phase A2b — Filing PDFs (no extra agents)")
            trace.begin("filings")
            gated = expand_filings(
                gated, session=getattr(client, "session", None),
                max_n=max_llm, progress=update,
            )
            pdf_n = sum(1 for e in gated if e.get("full_filing_available"))
            amount_n = sum(1 for e in gated if e.get("amount_inr_cr"))
            amount_lines = [
                f"{e.get('ticker')} python_type={e.get('event_type')} "
                f"amount={e.get('amount_inr_cr')} src={e.get('source_id')}"
                for e in gated[:20]
            ]
            trace.add(
                step_id="filings",
                name="PDF filings",
                kind="python",
                receives_from=["Liquidity gate"],
                sends_to=["Event extract"],
                received=f"{len(gated)} sourced announcements (source_id stamped)",
                passed=(
                    f"PDFs retrieved={pdf_n}. Python order amounts parsed={amount_n}.\n"
                    + "\n".join(amount_lines)
                ),
                parsed={"pdfs": pdf_n, "python_amounts": amount_n},
                note="Order amount is parsed from work-order language, not the largest rupee figure (order book).",
            )

            mentions = news_mention_counts(universe, progress=update)
            update("Phase A2c — Event extraction (python_type is locked)")
            trace.begin("extract")
            extracted = extract_events(gated, max_events=max_llm, progress=update)
            extracted = [e for e in extracted if e.get("ticker") in allowed]
            by_src = {e.get("source_id"): e for e in gated}
            for item in extracted:
                src = by_src.get(item.get("source_id")) or {}
                if src.get("amount_inr_cr") and (
                    item.get("event_type") in {"large_order_win", "export_order", "new_customer"}
                ):
                    item["amount_inr_cr"] = src["amount_inr_cr"]
                item["full_filing_available"] = bool(src.get("full_filing_available"))
                item["filing_text"] = src.get("filing_text") or item.get("filing_text") or ""
                item["subject"] = src.get("subject") or item.get("subject")
                item["source_text"] = item.get("subject") or src.get("subject") or ""
            for ev in gated:
                ev["filing_text"] = ""
            extract_lines = [
                f"{e.get('ticker')} type={e.get('event_type')} "
                f"amount={e.get('amount_inr_cr')} src={e.get('source_id')} "
                f"{(e.get('subject') or '')[:100]}"
                for e in extracted[:25]
            ]
            trace.add(
                step_id="extract",
                name="Event extract",
                kind="muse",
                receives_from=["PDF filings", "python_type on each source_id"],
                sends_to=["Materiality"],
                received="\n".join(
                    f"[{e.get('source_id')}] {e.get('ticker')} python_type={e.get('event_type')} "
                    f"{(e.get('subject') or '')[:140]}"
                    for e in gated[:25]
                ),
                passed="\n".join(extract_lines) or "(none)",
                parsed={
                    "extracted": len(extracted),
                    "types": _count(extracted, "event_type"),
                },
                note="python_type is authoritative. LLM must not reclassify. Amounts from Python win over LLM.",
            )

            update("Phase A3 — Economic materiality + information awareness")
            trace.begin("materiality")
            scored = score_opportunities(
                extracted, names, cfg, progress=update, news_mentions=mentions,
            )
            groups = cluster_events(scored)
            per_ticker = int(cfg.get("catalyst_cards", {}).get("max_cards_per_ticker", 1))
            cards = pick_cluster_heads(groups, max_per_ticker=per_ticker)
            cards = sorted(
                cards,
                key=lambda c: (
                    (c.get("materiality") or {}).get("score") or 0,
                    c.get("rank_score") or 0,
                ),
                reverse=True,
            )
            trace.add(
                step_id="materiality",
                name="Materiality",
                kind="python",
                receives_from=["Structured events"],
                sends_to=["Episodes", "Evidence expand"],
                received=_events_brief(extracted),
                passed=_cards_brief(cards),
                parsed=_stage_counts(cards),
                note="Interpretation is generated from event_type on the evidence object. Full-PDF keyword soup cannot reclassify.",
            )

        horizon = int(cfg.get("catalyst_cards", {}).get("horizon_days", 30))
        written = 0
        if cards:
            update("Phase A4 — Writing observation-only episodes")
            trace.begin("episodes")
            written = write_discovery_episodes(cards, run_id, horizon_days=horizon)
            trace.add(
                step_id="episodes",
                name="Episodes",
                kind="python",
                receives_from=["Materiality"],
                sends_to=["(observation store)"],
                received=f"{len(cards)} cards",
                passed=f"{written} observation-only episodes. Not used to retune frozen weights.",
                parsed={"episodes_written": written},
            )

        if any(
            c.get("stage") == "opportunity_candidate"
            or (
                c.get("stage") == "event_lead"
                and c.get("event_type") in {"large_order_win", "export_order"}
            )
            for c in cards
        ):
            update("Phase A5 — Evidence expansion on opportunity candidates only (not more scoring)")
            trace.begin("expansion")
            expansion_packs = expand_candidates(cards, progress=update)
            exp_lines = [
                f"{p.get('ticker')} verdict={p.get('verdict')} open={p.get('open_questions')} "
                f"path={p.get('report_path')}"
                for p in expansion_packs
            ]
            trace.add(
                step_id="expansion",
                name="Evidence expand",
                kind="python",
                receives_from=["Opportunity candidates"],
                sends_to=["Report", "Council (later)"],
                received=_cards_brief(
                    [c for c in cards if c.get("stage") == "opportunity_candidate"]
                    or cards[:3]
                ),
                passed="\n".join(exp_lines) or "(none)",
                parsed={
                    "packs": [
                        {
                            "ticker": p.get("ticker"),
                            "verdict": p.get("verdict"),
                            "open_questions": p.get("open_questions"),
                            "report_path": p.get("report_path"),
                        }
                        for p in expansion_packs
                    ]
                },
                note="Council must not rediscover the event. It receives this pack.",
            )

        meta = {
            "run_id": run_id,
            "universe_n": uni_n,
            "raw_events": raw_n,
            "gated_events": len(gated),
            "llm_events": min(len(gated), int(radar.get("max_events_to_llm", 40))),
            "min_adv_inr": uni_cfg.get("min_adv_inr"),
            "mcap_min_cr": uni_cfg.get("mcap_min_cr"),
            "microcap_max_cr": uni_cfg.get("microcap_max_cr"),
            "mcap_max_cr": uni_cfg.get("microcap_max_cr"),
            "weights": frozen_weights(cfg),
            "empty_reason": empty_reason,
            "episodes_written": written,
            "expansion_reports": [p.get("report_path") for p in expansion_packs if p.get("report_path")],
        }
        update("Phase A6 — Writing catalyst report + agent trace")
        trace.begin("report")
        report = generate_catalyst_report(cards, meta)
        REPORTS.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = REPORTS / f"discovery_catalyst_{stamp}.md"
        path.write_text(report, encoding="utf-8")
        trace.add(
            step_id="report",
            name="Report",
            kind="python",
            receives_from=["Materiality", "Evidence expand"],
            sends_to=["UI / markdown"],
            received=_cards_brief(cards),
            passed=report[:2500],
            parsed={"report_path": str(path), **_stage_counts(cards)},
        )
        trace_path = REPORTS / f"discovery_trace_{stamp}.md"
        trace_path.write_text(trace_to_markdown(trace.as_dict()), encoding="utf-8")
        update(f"Report saved: {path}")
        update(f"Agent trace saved: {trace_path}")
        return {
            "run_id": run_id,
            "report_path": str(path),
            "trace_path": str(trace_path),
            "trace": trace.as_dict(),
            "cards": cards,
            "universe_n": meta["universe_n"],
            "gated_events": meta["gated_events"],
            "episodes_written": written,
            "empty_reason": empty_reason,
            "weights": meta["weights"],
            "expansion_reports": meta.get("expansion_reports") or [],
        }


def _count(rows: list[dict], key: str) -> dict:
    out = {}
    for row in rows:
        val = str(row.get(key) or "unknown")
        out[val] = out.get(val, 0) + 1
    return out


def _stage_counts(cards: list[dict]) -> dict:
    return {
        "opportunity_candidates": sum(1 for c in cards if c.get("stage") == "opportunity_candidate"),
        "event_leads": sum(1 for c in cards if c.get("stage") == "event_lead"),
        "discarded": sum(1 for c in cards if c.get("stage") == "discard_lead"),
    }


def _events_brief(events: list[dict]) -> str:
    lines = []
    for e in events[:20]:
        lines.append(
            f"{e.get('ticker')} type={e.get('event_type')} amount={e.get('amount_inr_cr')} "
            f"src={e.get('source_id')}"
        )
    extra = len(events) - min(20, len(events))
    if extra > 0:
        lines.append(f"… and {extra} more")
    return "\n".join(lines) or "(none)"


def _cards_brief(cards: list[dict]) -> str:
    lines = []
    for c in cards[:20]:
        mat = c.get("materiality") or {}
        lines.append(
            f"{c.get('ticker')} stage={c.get('stage')} type={c.get('event_type')} "
            f"mat={mat.get('score')}/5 amount={c.get('amount_inr_cr') or mat.get('amount_inr_cr')} "
            f"vs_rev={mat.get('order_to_revenue')} reason={mat.get('reason')}"
        )
    extra = len(cards) - min(20, len(cards))
    if extra > 0:
        lines.append(f"… and {extra} more")
    return "\n".join(lines) or "(none)"


def main():
    result = DiscoveryOrchestrator().run()
    print("REPORT", result.get("report_path"), flush=True)
    print("TRACE", result.get("trace_path"), flush=True)
    print("CARDS", len(result.get("cards") or []), flush=True)
    print("UNIVERSE", result.get("universe_n"), flush=True)
    print("EPISODES", result.get("episodes_written"), flush=True)
    print("EXPANSION", result.get("expansion_reports"), flush=True)


if __name__ == "__main__":
    main()
