"""Discovery Phase A.1: tiers, unknown≠zero, materiality, provenance. No network."""
from __future__ import annotations

import pandas as pd
import pytest

from agents.discovery_config import frozen_weights, load_discovery_config
from agents.discovery_universe import apply_liquidity_gate, apply_mcap_gate, assign_tiers
from agents.event_filter import classify_subject, filter_announcements
from agents.event_provenance import (
    bind_extraction,
    cluster_events,
    pick_cluster_heads,
    source_supports_event_type,
)
from agents.opportunity_scorer import catalyst_score, scarcity_score


def test_frozen_weights_sum_to_one_and_are_locked():
    cfg = load_discovery_config()
    assert cfg["opportunity_score"]["frozen"] is True
    w = frozen_weights(cfg)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert cfg["universe"]["include_smallcap"] is False
    assert cfg["universe"]["primary_tiers"] == ["sme", "microcap"]


def test_liquidity_hard_gate_excludes_below_minimum():
    df = pd.DataFrame({
        "ticker": ["LIQUID", "THIN", "UNKNOWN"],
        "adv_inr": [8_000_000, 1_000_000, None],
        "turnover_inr": [9_000_000, 500_000, None],
    })
    kept = apply_liquidity_gate(df, min_adv_inr=5_000_000, unknown_is_exclude=True)
    assert list(kept["ticker"]) == ["LIQUID"]


def test_mcap_unknown_excluded_for_announcement_backdoor():
    df = pd.DataFrame({
        "ticker": ["NBCC", "SMECO"],
        "mcap_cr": [None, 800],
    })
    kept = apply_mcap_gate(df, 50, 1000, unknown_policy="exclude")
    assert list(kept["ticker"]) == ["SMECO"]


def test_tiers_do_not_mix_sme_and_smallcap():
    cfg = load_discovery_config()["universe"]
    df = pd.DataFrame({
        "ticker": ["EMERGECO", "MICROCO", "RAILTEL"],
        "source": ["NSE SME/Emerge", "NIFTY MICROCAP 250", "NIFTY SMALLCAP 250"],
        "exchange": ["NSE_SME", "NSE", "NSE"],
        "mcap_cr": [None, 400, 2500],
    })
    out = assign_tiers(df, cfg)
    assert out.set_index("ticker")["tier"].to_dict() == {
        "EMERGECO": "sme",
        "MICROCO": "microcap",
        "RAILTEL": "smallcap",
    }


def test_event_filter_keeps_order_drops_share_certificate():
    cfg = load_discovery_config()
    keep = classify_subject("Received a purchase order of Rs 50 crore", cfg)
    drop = classify_subject("Loss of share certificate — issue of duplicate", cfg)
    assert keep["keep"] is True
    assert drop["keep"] is False


def test_court_orders_passed_is_not_an_order_win():
    cfg = load_discovery_config()
    verdict = classify_subject(
        "Action(s) taken or orders passed | Railtel informed the Exchange about Action(s) taken or orders passed",
        cfg,
    )
    assert verdict["keep"] is False


def test_unknown_analyst_is_not_maximum_scarcity():
    cfg = load_discovery_config()["scarcity"]
    reaction = {"abs_return_pct": 1.2, "volume_ratio": 0.9}
    score, info = scarcity_score(None, reaction, cfg, analyst_status="unknown")
    assert score == pytest.approx(50.0)  # reaction only; analyst contributes 0
    assert "unknown" in info["analyst"]


def test_verified_zero_analysts_and_muted_participation():
    cfg = load_discovery_config()["scarcity"]
    reaction = {"abs_return_pct": 1.2, "volume_ratio": 0.9}
    score, info = scarcity_score(0, reaction, cfg, analyst_status="verified")
    assert score == 100.0
    assert info["awareness"] == "muted_with_participation"


def test_thin_volume_is_not_muted_awareness():
    cfg = load_discovery_config()["scarcity"]
    reaction = {"abs_return_pct": 1.8, "volume_ratio": 0.1}
    score, info = scarcity_score(0, reaction, cfg, analyst_status="verified")
    assert info["awareness"] == "thin_trading"
    assert score == pytest.approx(50.0)  # analyst 100 * 0.5, reaction 0


def test_missing_reaction_is_unknown_not_hidden():
    cfg = load_discovery_config()["scarcity"]
    score, info = scarcity_score(0, {}, cfg, analyst_status="verified")
    assert info["awareness"] == "unknown"
    assert score == pytest.approx(50.0)


def test_unknown_order_size_is_not_catalyst_90():
    score, mat = catalyst_score({"event_type": "large_order_win", "sentiment": 0.8}, {})
    assert score == pytest.approx(35.0)
    assert mat["status"] == "unknown"


def test_order_vs_revenue_materiality():
    weak, winfo = catalyst_score(
        {"event_type": "large_order_win", "amount_inr_cr": 10, "sentiment": 0.5},
        {"revenue_cr": 1000},
    )
    major, minfo = catalyst_score(
        {"event_type": "large_order_win", "amount_inr_cr": 200, "sentiment": 0.5},
        {"revenue_cr": 300},
    )
    assert weak < 40
    assert winfo["status"] == "weak"
    assert major > 90
    assert minfo["status"] == "major"


def test_negative_sentiment_cuts_catalyst_score():
    high, _ = catalyst_score(
        {"event_type": "large_order_win", "amount_inr_cr": 200, "sentiment": 0.8},
        {"revenue_cr": 300},
    )
    low, _ = catalyst_score(
        {"event_type": "large_order_win", "amount_inr_cr": 200, "sentiment": -0.8},
        {"revenue_cr": 300},
    )
    assert high > 80
    assert low < 40


def test_provenance_rejects_bess_claim_on_loa_filing():
    sources = {
        "src_1": {
            "source_id": "src_1",
            "event_id": "ev_1",
            "ticker": "ACMESOLAR",
            "event_type": "large_order_win",
            "subject": "Acme Solar informed the Exchange about receiving of Letter of Award.",
            "source_text": "Acme Solar informed the Exchange about receiving of Letter of Award.",
            "announced_at": "2026-08-28",
        }
    }
    bound = bind_extraction({
        "source_id": "src_1",
        "symbol": "ACMESOLAR",
        "event_type": "capacity_expansion",
        "catalyst": "Commissioning of BESS project",
        "amount_inr_cr": None,
    }, sources)
    assert bound is not None
    assert bound["event_type"] == "large_order_win"
    assert "Letter of Award" in bound["source_text"]
    assert not source_supports_event_type(bound["source_text"], "capacity_expansion")


def test_invented_amount_is_dropped():
    sources = {
        "src_1": {
            "source_id": "src_1",
            "event_id": "ev_1",
            "ticker": "KRYSTAL",
            "event_type": "large_order_win",
            "subject": "Bagging/Receiving of orders/contracts",
            "source_text": "Bagging/Receiving of orders/contracts",
            "announced_at": "2026-08-28",
        }
    }
    bound = bind_extraction({
        "source_id": "src_1",
        "event_type": "large_order_win",
        "amount_inr_cr": 500,
    }, sources)
    assert bound["amount_inr_cr"] is None


def test_event_clustering_collapses_same_company_duplicates():
    events = [
        {"ticker": "ACME", "event_type": "large_order_win", "subject": "Letter of Award received",
         "source_text": "Letter of Award received", "announced_at": "2026-08-28", "opportunity_score": 40},
        {"ticker": "ACME", "event_type": "large_order_win", "subject": "receiving of Letter of Award",
         "source_text": "receiving of Letter of Award", "announced_at": "2026-08-28", "opportunity_score": 38},
        {"ticker": "OTHER", "event_type": "preferential_issue", "subject": "preferential warrants",
         "source_text": "preferential warrants", "announced_at": "2026-08-28", "opportunity_score": 30},
    ]
    groups = cluster_events(events)
    heads = pick_cluster_heads(groups, max_per_ticker=1)
    tickers = [h["ticker"] for h in heads]
    assert tickers.count("ACME") == 1
    assert "OTHER" in tickers
    assert len(heads[0]["cluster_events"]) >= 1


def test_filter_announcements_only_returns_kept():
    cfg = load_discovery_config()
    rows = [
        {"ticker": "A", "subject": "Capacity expansion at new plant"},
        {"ticker": "B", "subject": "Trading window closure"},
    ]
    kept = filter_announcements(rows, cfg)
    assert [r["ticker"] for r in kept] == ["A"]


def test_phase_a_score_does_not_let_catalyst_override_zero_quality():
    weights = frozen_weights()
    components = {
        "catalyst": 100.0,
        "scarcity": 100.0,
        "quality": 0.0,
        "inflection": 0.0,
        "mispricing": 0.0,
    }
    total = sum(components[k] * weights[k] for k in weights)
    assert total == pytest.approx(45.0)


def test_md_appointment_is_minor_not_an_opportunity():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality({
        "event_type": "management_change",
        "source_text": "Appointment of Mr X as Managing Director w.e.f. December 19, 2026.",
        "subject": "Appointment",
    }, {})
    assert mat["score"] == 1
    assert mat["stage"] == "discard_lead"


def test_ncd_allotment_is_minor():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality({
        "event_type": "other_catalyst",
        "source_text": "allotment of 2500 Non Convertible Debentures",
        "subject": "Allotment of Securities",
    }, {})
    assert mat["score"] == 1


def test_unknown_order_is_lead_not_opportunity():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality({
        "event_type": "large_order_win",
        "source_text": "Bagging/Receiving of orders/contracts",
        "subject": "Bagging/Receiving of orders/contracts",
    }, {})
    assert mat["score"] == 2
    assert mat["stage"] == "event_lead"


def test_large_order_vs_revenue_is_transformational():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality(
        {"event_type": "large_order_win", "amount_inr_cr": 200, "source_text": "order of Rs 200 crore"},
        {"revenue_cr": 300},
    )
    assert mat["score"] == 5
    assert mat["stage"] == "opportunity_candidate"
    assert mat["order_to_revenue"] == pytest.approx(200 / 300)


def test_tiny_order_is_immaterial():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality(
        {"event_type": "large_order_win", "amount_inr_cr": 10, "source_text": "Rs 10 crore order"},
        {"revenue_cr": 1000},
    )
    assert mat["score"] == 1
    assert mat["stage"] == "discard_lead"


def test_order_win_pdf_with_promoter_table_does_not_become_promoter_buying():
    from agents.economic_materiality import economic_materiality
    from agents.event_record import interpretation_matches_type

    pdf = (
        "Work Order Intimation. Vivid Electromech bagging of orders/contracts.\n"
        "Shareholding pattern: promoter purchase of equity shares during the quarter.\n"
        "Promoter holding 62%."
    )
    mat = economic_materiality({
        "event_id": "ev_vivid",
        "ticker": "VIVIDEL",
        "event_type": "large_order_win",
        "subject": "Bagging/Receiving of orders/contracts | Vivid Electromech informed the Exchange about bagging/receiving of orders/contracts",
        "source_text": pdf,
        "filing_text": pdf,
    }, {})
    reason = (mat.get("reason") or "").lower()
    assert mat["score"] == 2
    assert "promoter" not in reason
    assert interpretation_matches_type("large_order_win", mat["reason"])
    assert not interpretation_matches_type(
        "large_order_win",
        "Promoter buying is a useful lead; stake size vs equity is not established.",
    )


def test_genxai_pit_is_promoter_purchase_not_management_change():
    cfg = load_discovery_config()
    subject = (
        "Updates | GenXAI Analytics Limited has informed the Exchange regarding "
        "'Disclosure under Regulation 7(2) of SEBI (PIT) Regulations, 2015, for "
        "purchase of 12000 shares by Rakesh Agarwal, Promotor and Managing Director"
    )
    verdict = classify_subject(subject, cfg)
    assert verdict["keep"] is True
    assert verdict["event_type"] == "promoter_purchase"

    sources = {
        "src_1": {
            "source_id": "src_1",
            "event_id": "ev_1",
            "ticker": "GENXAI",
            "event_type": "promoter_purchase",
            "subject": subject,
            "source_text": subject,
            "announced_at": "2026-08-25",
        }
    }
    bound = bind_extraction({
        "source_id": "src_1",
        "event_type": "management_change",
        "catalyst": "MD bought shares",
    }, sources)
    assert bound["event_type"] == "promoter_purchase"


def test_preferential_amount_is_not_shown_as_order_to_revenue():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality(
        {
            "event_type": "preferential_issue",
            "amount_inr_cr": 50000,
            "subject": "allotment of Fully Convertible Warrants on preferential basis",
        },
        {"revenue_cr": 36.5},
    )
    assert mat["score"] == 2
    assert mat["order_to_revenue"] is None


def test_ncd_in_filing_refines_preferential_to_fund_raise():
    sources = {
        "src_1": {
            "source_id": "src_1",
            "event_id": "ev_1",
            "ticker": "VIESL",
            "event_type": "preferential_issue",
            "subject": "Allotment of Securities",
            "filing_text": "Allotment of 2500 Non Convertible Debentures (NCDs).",
            "announced_at": "2026-08-26",
        }
    }
    bound = bind_extraction({
        "source_id": "src_1",
        "event_type": "preferential_issue",
    }, sources)
    assert bound["event_type"] == "fund_raise"


def test_chavda_order_parse_is_not_the_order_book():
    from agents.filing_expand import parse_order_crore, parse_rupee_crore
    text = (
        "Intimation of bagging of work order worth ₹54.72 crores (excluding GST) from Weisdom Group. "
        "the unexecuted order book as on date stands at nearly ₹846.92 crores."
    )
    assert parse_order_crore(text) == pytest.approx(54.72)
    assert parse_rupee_crore(text) == pytest.approx(846.92)


def test_python_order_amount_wins_over_llm_order_book_number():
    sources = {
        "src_1": {
            "source_id": "src_1",
            "event_id": "ev_1",
            "ticker": "CHAVDA",
            "event_type": "large_order_win",
            "subject": "Bagging/Receiving of orders/contracts",
            "filing_text": (
                "work order worth ₹54.72 crores from Weisdom. "
                "unexecuted order book ₹846.92 crores"
            ),
            "amount_inr_cr": 54.72,
            "announced_at": "2026-08-26",
        }
    }
    bound = bind_extraction({
        "source_id": "src_1",
        "event_type": "large_order_win",
        "amount_inr_cr": 846.92,
    }, sources)
    assert bound["amount_inr_cr"] == pytest.approx(54.72)


def test_expansion_fallback_prefers_work_order_with_book_over_largest_rupee():
    from agents.candidate_expansion import expand_candidates
    vinyas = {
        "ticker": "VINYAS",
        "stage": "event_lead",
        "event_type": "large_order_win",
        "amount_inr_cr": 109.8,
        "full_filing_available": True,
        "filing_text": "Award of new orders amounting to Rs 109.8 crore.",
        "subject": "Bagging/Receiving of orders/contracts",
        "materiality": {"reason": "Order of ₹109.8 Cr stated"},
        "market_awareness": {},
    }
    chavda = {
        "ticker": "CHAVDA",
        "stage": "event_lead",
        "event_type": "large_order_win",
        "amount_inr_cr": 54.72,
        "full_filing_available": True,
        "filing_text": (
            "work order worth ₹54.72 crores from Weisdom. "
            "unexecuted order book as on date stands at nearly ₹846.92 crores."
        ),
        "subject": "Bagging/Receiving of orders/contracts",
        "materiality": {"reason": "Order of ₹54.72 Cr stated"},
        "market_awareness": {},
    }
    # Don't hit the network: only test target selection via _lead_rank
    from agents.candidate_expansion import _lead_rank
    assert _lead_rank(chavda) > _lead_rank(vinyas)


def test_parse_rupee_crore_from_filing_text():
    from agents.filing_expand import parse_order_crore, parse_rupee_crore
    text = "Tejas Networks received an LOI valued at Rs.1537 Crores from TCS."
    assert parse_rupee_crore(text) == pytest.approx(1537.0)
    assert parse_order_crore(text) == pytest.approx(1537.0)


def test_chavda_order_amount_is_not_the_order_book():
    from pathlib import Path
    from agents.filing_expand import parse_order_crore, parse_rupee_crore
    root = Path(__file__).resolve().parent.parent
    matches = list((root / "cache" / "discovery" / "filings").glob("*CHAVDA*Weisdom*"))
    assert matches
    text = matches[0].read_text(encoding="utf-8", errors="replace")
    assert parse_rupee_crore(text) == pytest.approx(846.92)
    assert parse_order_crore(text) == pytest.approx(54.72)


def test_chavda_filing_parses_order_book_not_just_the_headline_order():
    from agents.candidate_expansion import _facts_from_card, _verdict
    filing = (
        "Intimation of bagging of work order worth ₹54.72 crores (excluding GST) from Weisdom Group, "
        "to be executed in the next 24 months. WEISDOM DESIGN BUILD LLP. "
        "ordinary course of business? Yes. related party transactions? No. "
        "The Company has received orders worth ₹144.17 crores during the current financial year and "
        "the unexecuted order book as on date stands at nearly ₹846.92 crores."
    )
    facts = _facts_from_card(
        {"amount_inr_cr": 54.72, "event_type": "large_order_win"},
        "Bagging/Receiving of orders/contracts",
        filing,
    )
    assert facts["order_book_cr"] == pytest.approx(846.92)
    assert facts["fy_orders_cr"] == pytest.approx(144.17)
    assert facts["customer"] == "WEISDOM DESIGN BUILD LLP"
    assert facts["related_party"] is False
    assert _verdict(
        {"materiality": {"mcap_cr": 25}},
        facts,
        {"revenue_cr": None, "mcap_cr": 25},
        [{"id": "Q1", "status": "disclosed"}],
    ) == "council_with_gaps"


def test_vividel_order_is_not_explained_as_promoter_buying():
    from agents.economic_materiality import economic_materiality
    from agents.event_record import interpretation_matches_type
    pdf = (
        "Work Order Intimation. The company has received purchase orders. "
        "Annexure: Promoter holding 62%. Promoter purchase of equity shares "
        "as per shareholding pattern."
    )
    event = {
        "event_id": "ev_vividel",
        "source_id": "src_vividel",
        "ticker": "VIVIDEL",
        "event_type": "large_order_win",
        "subject": "Bagging/Receiving of orders/contracts | Vivid Electromech informed the Exchange about bagging/receiving of orders/contracts",
        "filing_text": pdf,
    }
    mat = economic_materiality(event, {})
    assert event["event_type"] == "large_order_win"
    assert event["evidence"]["event_type"] == "large_order_win"
    assert event["evidence"]["source_text"].startswith("Bagging")
    assert "promoter" not in mat["reason"].lower()
    assert interpretation_matches_type("large_order_win", mat["reason"])
    assert not interpretation_matches_type(
        "large_order_win",
        "Promoter buying is a useful lead; stake size vs equity is not established.",
    )


def test_genxai_pit_is_promoter_purchase_not_management_change():
    cfg = load_discovery_config()
    subject = (
        "Updates | GenXAI Analytics Limited has informed the Exchange regarding "
        "'Disclosure under Regulation 7(2) of SEBI (PIT) Regulations, 2015, for "
        "purchase of 12000 shares by Rakesh Agarwal, Promotor and Managing Director"
    )
    verdict = classify_subject(subject, cfg)
    assert verdict["keep"] is True
    assert verdict["event_type"] == "promoter_purchase"


def test_python_event_type_is_not_overridden_by_llm():
    sources = {
        "src_1": {
            "source_id": "src_1",
            "event_id": "ev_1",
            "ticker": "VIVIDEL",
            "event_type": "large_order_win",
            "subject": "Bagging/Receiving of orders/contracts",
            "filing_text": "Promoter purchase of shares. Shareholding pattern.",
            "announced_at": "2026-08-25",
        }
    }
    bound = bind_extraction({
        "source_id": "src_1",
        "event_type": "management_change",
        "catalyst": "Promoter buying",
        "why_it_matters": "Promoter buying is a useful lead",
    }, sources)
    assert bound["event_type"] == "large_order_win"
    assert bound["source_text"] == "Bagging/Receiving of orders/contracts"


def test_preferential_issue_does_not_report_fake_order_to_revenue():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality(
        {
            "event_type": "preferential_issue",
            "amount_inr_cr": 50000,
            "subject": "allotment of Fully Convertible Warrants on preferential basis",
        },
        {"revenue_cr": 36.5},
    )
    assert mat["order_to_revenue"] is None
    assert mat["score"] == 2


def test_ncd_filing_refines_preferential_to_fund_raise():
    from agents.economic_materiality import economic_materiality
    mat = economic_materiality(
        {
            "event_type": "preferential_issue",
            "subject": "Allotment of Securities",
            "filing_text": "allotment of 2500 Non Convertible Debentures (NCDs)",
        },
        {},
    )
    assert mat["score"] == 1


def test_chavda_filing_exposes_order_book_not_just_mcap():
    from pathlib import Path
    from agents.candidate_expansion import _facts_from_card
    root = Path(__file__).resolve().parent.parent
    matches = list((root / "cache" / "discovery" / "filings").glob("*CHAVDA*Weisdom*"))
    assert matches, "cached CHAVDA Weisdom filing missing"
    filing = matches[0].read_text(encoding="utf-8", errors="replace")
    facts = _facts_from_card(
        {"amount_inr_cr": 54.72},
        "Bagging/Receiving of orders/contracts",
        filing,
    )
    assert facts["amount_inr_cr"] == pytest.approx(54.72)
    assert facts["order_book_cr"] == pytest.approx(846.92)
    assert facts["ordinary_course"] is True
    assert "WEISDOM" in (facts["customer"] or "").upper()
