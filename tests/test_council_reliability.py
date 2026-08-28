"""Council reliability: evidence slices, Chartist scalars, canonical Editor."""
from __future__ import annotations

import numpy as np
import pandas as pd

from agents.editor_canonical import align_parsed, enforce, is_consistent, memo_verdict_token
from agents.evidence_acquisition import EvidencePackage
from agents.technical_compute import compute_snapshot_from_ohlcv, snapshot_is_valid


def _ohlcv(n=260, multiindex=False) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    high = close + rng.uniform(0.2, 1.5, n)
    low = close - rng.uniform(0.2, 1.5, n)
    open_ = close + rng.normal(0, 0.3, n)
    volume = rng.integers(1_000_000, 5_000_000, n)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )
    if multiindex:
        df.columns = pd.MultiIndex.from_product([df.columns, ["RELIANCE.NS"]])
    return df


def test_chartist_snapshot_scalars_not_series():
    snap = compute_snapshot_from_ohlcv(_ohlcv(multiindex=True), ticker="RELIANCE")
    assert snap["valid"] is True
    for key in ("price", "sma20", "sma50", "sma200", "rsi"):
        assert isinstance(snap[key], float), key
    # The old bug: comparing Series in an if.
    assert snap["trend"] in ("up", "down")
    assert snapshot_is_valid(snap)


def test_chartist_rejects_short_history():
    snap = compute_snapshot_from_ohlcv(_ohlcv(n=10), ticker="X")
    assert snap["valid"] is False
    assert snapshot_is_valid(snap) is False


def test_quant_slice_excludes_news():
    pkg = EvidencePackage(ticker="RELIANCE", as_of="2026-08-28", yf_symbol="RELIANCE.NS")
    pkg.add("financials", "roe", 0.12, "test")
    pkg.add("news", "headline_1", "Something happened", "test")
    quant = pkg.for_role("quant")
    scout = pkg.for_role("scout")
    assert [i.label for i in quant] == ["roe"]
    assert [i.label for i in scout] == ["headline_1"]
    bull = pkg.for_role("debate")
    bear = pkg.for_role("debate")
    assert [i.id for i in bull] == [i.id for i in bear]
    assert {i.id for i in bull} == {"E001", "E002"}


def test_editor_json_wins_over_avoid_watchlist_memo():
    memo = """# Investment Analysis: RELIANCE

## 1. Executive Summary
- **Verdict**: Avoid (Insufficient Disclosure - Watchlist)
- **Target Horizon**: 1-3 Years
"""
    parsed = {
        "thesis": "neutral",
        "confidence": 0.25,
        "prediction_direction": "flat",
        "horizon_days": 30,
        "final_decision": "watch",
        "evidence": [],
        "risks": [],
    }
    fixed, canonical, already = enforce(memo, parsed)
    assert already is False
    assert canonical["final_decision"] == "watch"
    assert canonical["thesis"] == "neutral"
    assert canonical["prediction_direction"] == "flat"
    assert memo_verdict_token(fixed) == "watch"
    assert is_consistent(fixed, canonical)
    assert "Avoid" not in (memo_verdict_token(fixed) or "")


def test_editor_aligns_thesis_to_decision_but_not_30day_signal():
    canonical = align_parsed({
        "final_decision": "buy",
        "thesis": "bearish",
        "prediction_direction": "flat",
    })
    assert canonical["thesis"] == "bullish"
    assert canonical["investment_thesis"]["stance"] == "buy"
    assert canonical["prediction_direction"] == "flat"
    assert canonical["prediction"]["horizon_days"] == 30


def test_editor_keeps_independent_30day_signal():
    memo = """# Investment Analysis: RELIANCE

## 1. Executive Summary
- **Verdict**: Buy
- **Target Horizon**: 1-3 Years
"""
    parsed = {
        "final_decision": "watch",
        "prediction_direction": "negative",
        "horizon_days": 30,
    }
    fixed, canonical, _ = enforce(memo, parsed)
    assert canonical["final_decision"] == "watch"
    assert canonical["prediction"]["direction"] == "negative"
    assert memo_verdict_token(fixed) == "watch"
    assert "30-Day Signal" in fixed
    assert "Negative" in fixed
    assert "Investment Horizon" in fixed or "1-3 Years" in fixed


def test_chartist_cannot_cite_company_name_ids():
    from agents.evidence_validator import validate

    pkg = EvidencePackage(ticker="RELIANCE", as_of="2026-08-28", yf_symbol="RELIANCE.NS")
    pkg.add("financials", "company_name", "RELIANCE INDUSTRIES LTD", "test")
    pkg.add("financials", "sector", "Energy", "test")
    pkg.add("financials", "industry", "Oil", "test")
    pkg.add("financials", "market_cap", 1, "test")
    pkg.add("financials", "trailing_pe", 23.0, "test")
    pkg.add("market", "price", 1298.0, "python.technical_compute")
    pkg.add("market", "sma20", 1313.0, "python.technical_compute")
    pkg.add("market", "sma50", 1305.0, "python.technical_compute")
    pkg.add("market", "sma200", 1392.0, "python.technical_compute")
    pkg.add("market", "rsi", 45.7, "python.technical_compute")
    snap = {"price": 1298.0, "sma20": 1313.0, "sma50": 1305.0, "sma200": 1392.0, "rsi": 45.7}
    parsed = {
        "evidence_ids": ["E001", "E002", "E003", "E004", "E005"],
        "thesis": "neutral",
    }
    out = validate(parsed, pkg, "chartist", snapshot=snap)
    assert out["evidence_ids"] == ["E006", "E007", "E008", "E009", "E010"]
    assert out["invalid_evidence_ids"] == ["E001", "E002", "E003", "E004", "E005"]
    assert out["attribution_source"] == "python.technical_compute"
    assert "E001" not in out["evidence_ids"]


def test_quant_labels_map_and_out_of_scope_ids_drop():
    from agents.evidence_validator import validate

    pkg = EvidencePackage(ticker="RELIANCE", as_of="2026-08-28", yf_symbol="RELIANCE.NS")
    pkg.add("financials", "trailing_pe", 23.2, "test")
    pkg.add("news", "headline_1", "x", "test")
    parsed = {
        "evidence_ids": ["E002", "E999"],
        "evidence_labels": ["trailing_pe"],
    }
    out = validate(parsed, pkg, "quant")
    assert out["evidence_ids"] == ["E001"]
    assert "E002" in out["invalid_evidence_ids"]
    assert "E999" in out["invalid_evidence_ids"]
    assert out["validator_status"] == "repaired"


def test_debt_to_equity_percent_normalized():
    from agents.evidence_acquisition import _canonical_debt_to_equity
    ratio, note = _canonical_debt_to_equity(36.653)
    assert ratio == 0.36653
    assert "percent" in note


def test_canonical_price_is_not_an_evidence_item():
    pkg = EvidencePackage(ticker="RELIANCE", as_of="2026-08-28", yf_symbol="RELIANCE.NS")
    pkg.add("market", "price", 1298.0, "python.technical_compute")
    pkg.canonical = {
        "price": 1298.0,
        "quote_type": "latest_close",
        "live_price_quote": 1282.2,
    }
    labels = [i.label for i in pkg.items]
    assert "live_price_quote" not in labels
    assert "current_price" not in labels
    assert pkg.canonical["price"] == 1298.0

