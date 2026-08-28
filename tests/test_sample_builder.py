"""Sample builder: diversity, CHAVDA exclusion, pack parser has no CHAVDA fallbacks."""
from __future__ import annotations

from pathlib import Path

from agents.expansion_pack import parse_expansion_pack
from agents.sample_builder import pick_sample_cards, type_counts


def test_pick_sample_skips_chavda_and_diversifies_types():
    cards = [
        {"ticker": "CHAVDA", "event_type": "large_order_win", "stage": "opportunity_candidate",
         "event_id": "ev_2522b5ccc6", "full_filing_available": True,
         "materiality": {"score": 4}},
        {"ticker": "VIVIDEL", "event_type": "large_order_win", "stage": "event_lead",
         "event_id": "ev_vivid", "full_filing_available": True, "materiality": {"score": 2}},
        {"ticker": "GENXAI", "event_type": "promoter_purchase", "stage": "event_lead",
         "event_id": "ev_genx", "full_filing_available": True, "materiality": {"score": 2}},
        {"ticker": "UNIVASTU", "event_type": "preferential_issue", "stage": "event_lead",
         "event_id": "ev_uni", "full_filing_available": True, "materiality": {"score": 2}},
        {"ticker": "VIESL", "event_type": "fund_raise", "stage": "discard_lead",
         "event_id": "ev_viesl", "full_filing_available": True, "materiality": {"score": 1}},
        {"ticker": "KRYSTAL", "event_type": "large_order_win", "stage": "event_lead",
         "event_id": "ev_kryl", "full_filing_available": True, "materiality": {"score": 2}},
    ]
    picked = pick_sample_cards(cards, max_n=4, max_per_type=1)
    tickers = [c["ticker"] for c in picked]
    assert "CHAVDA" not in tickers
    types = type_counts(picked)
    assert types.get("large_order_win", 0) <= 1
    assert "promoter_purchase" in types or "preferential_issue" in types or "fund_raise" in types


def test_parse_expansion_does_not_invent_chavda_on_other_events():
    text = """
# Discovery · Evidence expansion — GENXAI
**Verdict:** `council_with_gaps`
- event_id: `ev_adb8c688c8`
- company: `GENXAI`
- event_type: `promoter_purchase`
- direction: `positive`
- source_id: `src_adb8c688c8`
- event_date: 25-Aug-2026 18:53:13
- source_text: Disclosure under Regulation 7(2)
- extracted_facts: none parsed
- economic_interpretation: Promoter purchase is a useful lead.
"""
    parsed = parse_expansion_pack(text, ticker="GENXAI")
    assert parsed["event_id"] == "ev_adb8c688c8"
    assert parsed["event_type"] == "promoter_purchase"
    assert parsed["customer"] is None
    assert parsed["amount_inr_cr"] is None
    assert parsed["event_id"] != "ev_2522b5ccc6"


def test_parse_chavda_pack_still_reads_order_amount():
    path = Path(__file__).resolve().parents[1] / "reports" / "discovery_expansion_CHAVDA_20260828_1800.md"
    parsed = parse_expansion_pack(path.read_text(encoding="utf-8"), ticker="CHAVDA")
    assert parsed["event_id"] == "ev_2522b5ccc6"
    assert parsed["event_type"] == "large_order_win"
    assert parsed["amount_inr_cr"] == 54.72
    assert parsed["customer"] == "WEISDOM DESIGN BUILD LLP"
    assert parsed["order_to_book"] == "6%"
