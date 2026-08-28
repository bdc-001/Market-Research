"""
Discovery Phase C — Council on an evidence-expanded candidate.

Does not change Phase A. Does not rediscover the filing.
Does not retune weights. Stores one observation episode.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from agents.agent_trace import TraceLog, trace_to_markdown
from agents.bull_bear_agents import BearAgent, BullAgent, FinancialAgent
from agents.common import setup_gemini
from agents.editor_agent import EditorAgent
from agents.episode_store import write_discovery_council_episode
from agents.evidence_acquisition import EvidencePackage
from agents.evidence_validator import validate as validate_lineage
from agents.expansion_pack import load_expansion_pack
from agents.prediction_format import UNKNOWN_PREDICTION, _clean_json
from agents.research_agent import ResearchAgent
from agents.technical_agent import TechnicalAgent
from agents.technical_compute import compute_snapshot_from_ohlcv, fetch_ohlcv, snapshot_is_valid

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
CACHE = ROOT / "cache" / "discovery" / "filings"

_LOCK = (
    "The event already exists. Do not rediscover or re-extract the filing. "
    "Investigate implications of the pack. If a fact has no ID, it is unknown. "
    "Never invent numbers."
)


def _entry_date(value) -> str | None:
    """Persist event_date as YYYY-MM-DD. Does not change Council reasoning."""
    if not value:
        return None
    text = str(value).strip()
    for fmt, n in (("%d-%b-%Y %H:%M:%S", 20), ("%d-%b-%Y", 11), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:n], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def run_chavda_council(progress_callback=None, pack_path: str | None = None) -> dict:
    return DiscoveryCouncil().run(
        ticker="CHAVDA",
        pack_path=pack_path,
        progress_callback=progress_callback,
    )


class DiscoveryCouncil:
    def run(self, ticker: str = "CHAVDA", pack_path: str | None = None, progress_callback=None) -> dict:
        update = progress_callback or (lambda m: print(m, flush=True))
        ticker = ticker.upper().strip()
        run_id = str(uuid.uuid4())
        trace = TraceLog("discovery_council", f"Discovery Council · {ticker}")

        update("Loading evidence pack (no new Discovery radar)...")
        trace.begin("pack")
        pack_file = Path(pack_path) if pack_path else _latest_expansion(ticker)
        package = pack_to_evidence(ticker, pack_file)
        event = package.acquisition.get("event") or {}
        debate = package.render("debate")
        index = package.render("editor", limit=80)
        trace.add(
            step_id="pack",
            name="Evidence pack",
            kind="python",
            receives_from=["Discovery expansion report"],
            sends_to=["Historian", "Quant", "Bull", "Bear", "Chartist"],
            received=str(pack_file),
            passed=f"{len(package.items)} items. event_id={event.get('event_id')} "
                   f"order={event.get('amount_inr_cr')} customer={event.get('customer')}",
            parsed={
                "pack_path": str(pack_file),
                "item_count": len(package.items),
                "event_id": event.get("event_id"),
                "source_id": event.get("source_id"),
            },
            note="Council does not scan filings. This pack is the only starting point.",
        )

        researcher = ResearchAgent()
        quant_agent = FinancialAgent()
        bull = BullAgent()
        bear = BearAgent()
        chartist = TechnicalAgent()
        editor = EditorAgent()
        for agent in (researcher, quant_agent, bull, bear, chartist, editor):
            agent.model = setup_gemini(with_memory=False)

        def enforce(agent, role, snapshot=None):
            parsed = getattr(agent, "last_parsed", None)
            if parsed is None:
                return
            validate_lineage(parsed, package, role, snapshot=snapshot)

        update("Historian: verifying business, order, customer, execution...")
        trace.begin("research")
        research = _run_research(researcher, ticker, debate)
        enforce(researcher, "debate")
        trace.add_agent(
            researcher, step_id="research", name="Historian (Research)",
            receives_from=["Evidence pack"], sends_to=["Editor"], received=debate,
        )

        update("Financial: revenue, book, margin scenarios, earnings impact...")
        trace.begin("financial")
        finance = _run_financial(quant_agent, ticker, debate)
        enforce(quant_agent, "debate")
        trace.add_agent(
            quant_agent, step_id="financial", name="Quant (Financials)",
            receives_from=["Evidence pack"], sends_to=["Editor"], received=debate,
        )

        update("Bull: strongest asymmetric case from this pack only...")
        trace.begin("bull")
        bull_case = _run_bull(bull, ticker, debate)
        enforce(bull, "debate")
        trace.add_agent(
            bull, step_id="bull", name="Bull",
            receives_from=["Evidence pack (shared)"], sends_to=["Editor"], received=debate,
        )

        update("Bear: attack the thesis from the same pack...")
        trace.begin("bear")
        bear_case = _run_bear(bear, ticker, debate)
        enforce(bear, "debate")
        trace.add_agent(
            bear, step_id="bear", name="Bear",
            receives_from=["Evidence pack (shared)"], sends_to=["Editor"], received=debate,
        )

        update("Technical: price/volume vs catalyst; unknown if snapshot missing...")
        trace.begin("technical")
        tech_text = _run_technical(chartist, ticker, package)
        enforce(chartist, "chartist", snapshot=package.market_snapshot)
        snap = chartist.last_snapshot or {}
        tech_received = "\n".join(f"{k}: {v}" for k, v in snap.items()) or "(invalid snapshot)"
        trace.add_agent(
            chartist, step_id="technical", name="Chartist (Technicals)",
            receives_from=["Python snapshot + pack tape"], sends_to=["Editor"],
            received=tech_received,
        )

        update("Editor: one canonical BUY / WATCH / REJECT...")
        editor_received = (
            f"── ticker ──\n{ticker}\n\n"
            f"── evidence pack index ──\n{index}\n\n"
            f"── Historian ──\n{research}\n\n"
            f"── Financial ──\n{finance}\n\n"
            f"── Bull ──\n{bull_case}\n\n"
            f"── Bear ──\n{bear_case}\n\n"
            f"── Technical ──\n{tech_text}"
        )
        trace.begin("editor")
        memo = _run_editor(
            editor, ticker, research, finance, bull_case, bear_case, tech_text, index,
        )
        enforce(editor, "editor")
        _lift_discovery_fields(editor)
        memo, decision = _patch_discovery_verdict(memo, editor.last_parsed)
        editor.last_prose = memo
        trace.add_agent(
            editor, step_id="editor", name="Editor",
            receives_from=["Historian", "Quant", "Bull", "Bear", "Chartist"],
            sends_to=["Episode store"],
            received=editor_received,
        )

        agents = {
            "research": researcher,
            "financial": quant_agent,
            "bull": bull,
            "bear": bear,
            "technical": chartist,
            "editor": editor,
        }
        update("Storing observation episode (no weight changes)...")
        trace.begin("episode")
        episode_id = write_discovery_council_episode(
            ticker, run_id, agents,
            event_id=str(event.get("event_id") or ""),
            source_id=str(event.get("source_id") or ""),
            evidence=package.as_dict(),
            editor_decision=decision,
            entry_date=_entry_date(event.get("event_date")),
            event_type=str(event.get("event_type") or ""),
        )
        if episode_id:
            try:
                from agents.outcome_evaluator import evaluate_episode
                evaluate_episode(episode_id, fetch_prices=False)
            except Exception as exc:
                update(f"Outcome reserve skipped: {exc}")
        trace.add(
            step_id="episode",
            name="Episode store",
            kind="python",
            receives_from=["Editor"],
            sends_to=["(wait for 30d outcome)"],
            received=f"decision={decision} confidence={editor.last_parsed.get('confidence')}",
            passed=f"episode_id={episode_id} event_id={event.get('event_id')}",
            parsed={
                "episode_id": episode_id,
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "decision": decision,
                "entry_price": (package.canonical or {}).get("price") or snap.get("price"),
            },
            note="Do not modify Discovery or QuanTum from this conclusion.",
        )

        REPORTS.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        memo_path = REPORTS / f"discovery_council_{ticker}_{stamp}.md"
        trace_path = REPORTS / f"discovery_council_trace_{ticker}_{stamp}.md"
        memo_path.write_text(memo, encoding="utf-8")
        trace_path.write_text(trace_to_markdown(trace.as_dict()), encoding="utf-8")
        update(f"Council memo: {memo_path}")
        update(f"Council trace: {trace_path}")
        update(f"Episode: {episode_id}")
        return {
            "ticker": ticker,
            "run_id": run_id,
            "episode_id": episode_id,
            "decision": decision,
            "memo_path": str(memo_path),
            "trace_path": str(trace_path),
            "trace": trace.as_dict(),
            "parsed": editor.last_parsed,
            "event_id": event.get("event_id"),
            "entry_price": (package.canonical or {}).get("price") or snap.get("price"),
        }


def _latest_expansion(ticker: str) -> Path:
    matches = sorted(REPORTS.glob(f"discovery_expansion_{ticker}_*.md"))
    if not matches:
        raise FileNotFoundError(f"No expansion pack for {ticker} in {REPORTS}")
    return matches[-1]


def pack_to_evidence(ticker: str, pack_file: Path) -> EvidencePackage:
    parsed = load_expansion_pack(pack_file, ticker=ticker)
    as_of = datetime.now().strftime("%Y-%m-%d")
    pkg = EvidencePackage(ticker=ticker, as_of=as_of, yf_symbol=f"{ticker}.NS")
    src = str(pack_file)
    event_id = parsed.get("event_id")
    source_id = parsed.get("source_id")
    event_type = parsed.get("event_type")
    event_date = parsed.get("event_date")
    if not event_id:
        raise ValueError(f"Expansion pack missing event_id: {pack_file}")

    pkg.add("filings", "event_id", event_id, src, "immutable event identity")
    pkg.add("filings", "source_id", source_id, src)
    pkg.add("filings", "event_type", event_type, src)
    pkg.add("filings", "event_date", event_date, src)
    pkg.add("filings", "source_text", parsed.get("source_text"), src)
    pkg.add("filings", "order_inr_cr", parsed.get("amount_inr_cr"), src, "parsed amount if present")
    pkg.add("filings", "customer", parsed.get("customer"), src)
    pkg.add("filings", "gst_excluded", parsed.get("gst_excluded"), src)
    pkg.add("filings", "order_book_cr", parsed.get("order_book_cr"), src)
    pkg.add("filings", "fy_orders_cr", parsed.get("fy_orders_cr"), src)
    pkg.add("filings", "execution_months", parsed.get("execution_months"), src)
    pkg.add("filings", "economic_interpretation", parsed.get("interpretation"), src)
    pkg.add("filings", "expansion_verdict", parsed.get("verdict"), src)
    filing = _load_filing(ticker)
    if filing:
        pkg.add("filings", "filing_excerpt", filing[:2500], "nse_attachment")

    for key, value in (parsed.get("fundamentals") or {}).items():
        pkg.add("financials", key, value, "expansion_pack")
    pkg.add("financials", "debt_status", "unknown" if "total_debt_cr" not in (parsed.get("fundamentals") or {}) else "known", "expansion_pack")
    pkg.add("financials", "cash_flow_status", "unknown" if "fcf_cr" not in (parsed.get("fundamentals") or {}) else "known", "expansion_pack")
    pkg.add("financials", "order_to_revenue", parsed.get("order_to_revenue"), src)
    pkg.add("financials", "order_to_mcap", parsed.get("order_to_mcap"), src)
    pkg.add("financials", "order_to_book", parsed.get("order_to_book"), src)

    for slot in parsed.get("retrieval") or []:
        label = str(slot.get("label") or "retrieval").lower().replace(" ", "_")
        pkg.add("news", label, f"{slot.get('status')} — {slot.get('detail')}", src)

    for qid, title, body in parsed.get("questions") or []:
        pkg.add("filings", f"question_{qid}", f"{title} — {body}", src)

    pkg.add("market", "tape", parsed.get("tape"), src)
    pkg.add("market", "abnormal_return_5d_pct", parsed.get("abnormal_return_5d_pct"), src)
    pkg.add("market", "abnormal_volume", parsed.get("abnormal_volume"), src)

    try:
        ohlcv = fetch_ohlcv(ticker)
        snapshot = compute_snapshot_from_ohlcv(ohlcv, ticker=ticker)
    except Exception as exc:
        snapshot = {"valid": False, "error": str(exc)}
        pkg.errors.append(f"ohlcv: {exc}")
    pkg.market_snapshot = snapshot
    if snapshot_is_valid(snapshot):
        for key in (
            "price", "sma20", "sma50", "sma200", "rsi", "macd", "macd_signal",
            "atr", "volume", "volume_vs_average", "high_52w", "low_52w",
            "support", "resistance", "trend", "cross", "bars",
        ):
            pkg.add("market", key, snapshot.get(key), "python.technical_compute")
        pkg.canonical = {
            "price": snapshot.get("price"),
            "price_source": "python.technical_compute",
            "price_timestamp": snapshot.get("as_of"),
            "quote_type": "latest_close",
        }
    else:
        pkg.errors.append(snapshot.get("error") or "technical snapshot invalid")
        pkg.canonical = {"price": None, "price_source": None, "quote_type": None}

    pkg.acquisition["event"] = {
        "event_id": event_id,
        "source_id": source_id,
        "amount_inr_cr": parsed.get("amount_inr_cr"),
        "customer": parsed.get("customer"),
        "event_type": event_type,
        "event_date": event_date,
        "direction": parsed.get("direction"),
    }
    pkg.acquisition["pack_path"] = str(pack_file)
    return pkg


def _run_research(agent: ResearchAgent, ticker: str, package: str) -> str:
    prompt = f"""
You are the Historian for Discovery candidate {ticker}.
{_LOCK}

{package}

Task — answer from this pack only:
1. What business is this company in? Cite IDs. If absent, unknown.
2. What event is in the pack (event_type, date, amount/counterparty if present)? Cite IDs. Do not rediscover a different event.
3. What is known and unknown about any customer, counterparty, or related party?
4. Is there any historical execution, delivery, or prior similar-event outcome in the pack?
5. Does the pack show whether this event type previously became revenue, dilution, or a completed corporate action?

Do not search. Do not invent a customer or promoter story.
"""
    return agent.complete(prompt)


def _run_financial(agent: FinancialAgent, ticker: str, package: str) -> str:
    prompt = f"""
You are the Financial Analyst for Discovery candidate {ticker}.
{_LOCK}

{package}

Task — supplied numbers only:
1. Verify revenue, EBITDA, mcap, PE if those IDs exist. If missing, unknown.
2. Scale this event versus revenue, order book, mcap, or equity — only with IDs. If there is no amount, say unknown.
3. Give 3 economic scenarios (low/base/high) as assumptions, not facts (margin, dilution, or cash impact as relevant to event_type).
4. Can this event materially change earnings or capital structure? Show arithmetic only if IDs support it.
5. Debt, cash flow, latest quarterly: report unknown if no ID.

Output: earnings/capital impact = immaterial / incremental / major / unknown, with IDs.
"""
    return agent.complete(prompt)


def _run_bull(agent: BullAgent, ticker: str, package: str) -> str:
    prompt = f"""
You are Bull for Discovery candidate {ticker}.
{_LOCK}
You receive THE SAME pack as Bear. Do not claim the filing was not disclosed.

{package}

Build the strongest case that this is still asymmetric upside.
Explain exactly what the market may be missing.
Quantify potential earnings/value impact using only pack IDs.
If you cannot quantify, say unknown — do not invent a target price.
3 points, each: Claim / Evidence IDs / Interpretation / Assumption / Risk.
"""
    return agent.complete(prompt)


def _run_bear(agent: BearAgent, ticker: str, package: str) -> str:
    prompt = f"""
You are Bear for Discovery candidate {ticker}.
{_LOCK}
You receive THE SAME pack as Bull. Do not deny the filing exists.

{package}

Attack the thesis on whatever the pack actually contains:
- economic materiality (size vs revenue / book / equity / license if IDs exist)
- execution or completion risk
- margins, dilution, or cash proceeds (unknowns are gaps, not proof of distress)
- customer / counterparty / related-party credibility
- balance sheet unknowns
- tape / liquidity
- valuation (PE / mcap IDs)
Determine what would make the apparent catalyst misleading.
3 points, each: Claim / Evidence IDs / Interpretation / Assumption / Risk.
"""
    return agent.complete(prompt)


def _run_technical(agent: TechnicalAgent, ticker: str, package: EvidencePackage) -> str:
    snap = package.market_snapshot or {}
    agent.last_snapshot = snap
    if not snapshot_is_valid(snap):
        return agent.record_failure(
            "Technical snapshot invalid or unavailable. Tape/price reaction from the "
            "pack may still be cited by the Editor via market IDs. Do not invent levels."
        )
    id_map = package.label_id_map("market")
    legend = "\n".join(
        f"- {label} → {eid}" for label, eid in id_map.items()
    )
    prompt = f"""
Interpret already-computed technicals for {ticker} against the catalyst in the pack.
Do not recalculate. Do not invent. If a scalar is missing, unknown.

Canonical latest_close: {snap.get('price')}
SMA20/50/200: {snap.get('sma20')} / {snap.get('sma50')} / {snap.get('sma200')}
RSI: {snap.get('rsi')}  trend: {snap.get('trend')}  volume_vs_average: {snap.get('volume_vs_average')}
Pack tape (also in IDs): 5d |return| and volume ratio, tape=thin_trading.

Allowed evidence_labels / IDs:
{legend}

Question: does current price/volume SUPPORT or CONTRADICT the idea that this
event is an unpriced catalyst? Thin trading is not proof the market ignored it.
"""
    return agent.complete(prompt)


def _run_editor(agent, ticker, research, finance, bull_case, bear_case, technical, index) -> str:
    prompt = f"""
You are the Editor for Discovery candidate {ticker}.
{_LOCK}

Your only job: is this genuinely asymmetric, or is the apparent catalyst misleading?

Evidence pack index:
{index}

1. Historian: {research}
2. Financial: {finance}
3. Bull: {bull_case}
4. Bear: {bear_case}
5. Technical: {technical}

Write a short memo:

# Discovery Council: {ticker}

## Verdict
- **Verdict**: Buy | Watch | Reject
- **Catalyst valid**: yes / no / unknown
- **Economic materiality**: immaterial / incremental / major / unknown
- **Asymmetry**: yes / no / unknown
- **Confidence**: 0-1 (stored, never used to rank)

## Why
## What Bull got right
## What Bear got right
## Missing evidence
## Decision

JSON appendix MUST use final_decision as exactly one of: buy, watch, reject
(not avoid/hold). Also include:
  "catalyst_valid": true | false | "unknown",
  "economic_materiality": "immaterial" | "incremental" | "major" | "transformational" | "unknown",
  "asymmetry": true | false | "unknown",
  "key_evidence": ["..."],
  "key_risks": ["..."],
  "missing_evidence": ["..."]
"""
    return agent.complete(prompt)


def _lift_discovery_fields(editor) -> None:
    parsed = dict(editor.last_parsed or UNKNOWN_PREDICTION)
    extra = _clean_json(_json_tail(editor.last_raw or ""))
    for key in (
        "catalyst_valid", "economic_materiality", "asymmetry",
        "key_evidence", "key_risks", "missing_evidence",
    ):
        if key in extra:
            parsed[key] = extra[key]
    decision = str(parsed.get("final_decision") or extra.get("final_decision") or "").lower()
    decision = {
        "avoid": "reject", "sell": "reject", "hold": "watch",
        "strong_buy": "buy", "accumulate": "buy",
    }.get(decision, decision)
    if decision not in {"buy", "watch", "reject"}:
        decision = "watch"
    parsed["final_decision"] = decision
    editor.last_parsed = parsed


def _patch_discovery_verdict(memo: str, parsed: dict) -> tuple[str, str]:
    decision = str((parsed or {}).get("final_decision") or "watch").lower()
    if decision not in {"buy", "watch", "reject"}:
        decision = "watch"
    label = {"buy": "Buy", "watch": "Watch", "reject": "Reject"}[decision]
    text = memo or ""
    if re.search(r"^\s*[-*]?\s*\*\*Verdict\*\*\s*:", text, re.I | re.M):
        text = re.sub(
            r"^(\s*[-*]?\s*\*\*Verdict\*\*\s*:).*$",
            rf"\1 {label}",
            text, count=1, flags=re.I | re.M,
        )
    else:
        text = f"**Verdict**: {label}\n\n" + text
    return text, decision


def _json_tail(raw: str) -> str:
    if "|||PREDICTION|||" in raw:
        return raw.split("|||PREDICTION|||", 1)[-1]
    return raw


def _questions(text: str) -> list[tuple[str, str, str]]:
    out = []
    blocks = re.split(r"### (Q\d+)\.\s*", text)
    # split gives [preamble, Q1, body1, Q2, body2, ...]
    i = 1
    while i + 1 < len(blocks):
        qid = blocks[i]
        body = blocks[i + 1]
        title = (body.split("\n", 1)[0] or "").strip()
        out.append((qid, title, body.strip()[:800]))
        i += 2
    return out


def _load_filing(ticker: str) -> str:
    ticker = (ticker or "").upper()
    if not ticker or not CACHE.exists():
        return ""
    matches = sorted(CACHE.glob(f"*{ticker}*"))
    if not matches:
        return ""
    return matches[0].read_text(encoding="utf-8", errors="replace")[:4000]


def _field(text: str, pattern: str):
    match = re.search(pattern, text or "", re.I)
    if not match:
        return None
    return match.group(1).strip()


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _maybe_num(value):
    n = _num(value)
    return n if n is not None else value


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="CHAVDA")
    parser.add_argument("--pack", default="")
    args = parser.parse_args()
    if args.ticker.upper() == "CHAVDA" and not args.pack:
        result = run_chavda_council()
    else:
        result = DiscoveryCouncil().run(
            ticker=args.ticker,
            pack_path=args.pack or None,
        )
    print("MEMO", result.get("memo_path"), flush=True)
    print("TRACE", result.get("trace_path"), flush=True)
    print("DECISION", result.get("decision"), flush=True)
    print("EPISODE", result.get("episode_id"), flush=True)
    print("EVENT", result.get("event_id"), flush=True)
    parsed = result.get("parsed") or {}
    print("FIELDS", json.dumps({
        "final_decision": parsed.get("final_decision"),
        "catalyst_valid": parsed.get("catalyst_valid"),
        "economic_materiality": parsed.get("economic_materiality"),
        "asymmetry": parsed.get("asymmetry"),
        "confidence": parsed.get("confidence"),
    }, default=str), flush=True)


if __name__ == "__main__":
    main()
