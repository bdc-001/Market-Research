"""Phase 2A: prediction vs recommendation vs council decision stay separate."""
from __future__ import annotations

from datetime import date

import pandas as pd

from agents.episode_store import split_agent_calls
from agents.outcome_evaluator import (
    FLAT_BAND,
    compute_horizon_metrics,
    direction_correct,
    horizon_elapsed,
    watch_decision_quality,
)


def test_split_does_not_overwrite_direction_with_recommendation():
    direction, rec = split_agent_calls({
        "prediction_direction": "positive",
        "final_decision": "buy",
    }, "bull")
    assert direction == "positive"
    assert rec == "buy"


def test_split_maps_avoid_to_reject_and_keeps_flat_prediction():
    direction, rec = split_agent_calls({
        "prediction_direction": "flat",
        "thesis": "bearish",
        "final_decision": "avoid",
    }, "bear")
    assert direction == "flat"
    assert rec == "reject"


def test_split_does_not_infer_direction_from_buy():
    direction, rec = split_agent_calls({
        "final_decision": "buy",
    }, "bull")
    assert direction is None
    assert rec == "buy"


def test_editor_watch_is_recommendation_not_council_overwrite():
    direction, rec = split_agent_calls({
        "prediction_direction": "flat",
        "final_decision": "watch",
    }, "editor")
    assert direction == "flat"
    assert rec == "watch"


def test_direction_correct_positive_negative_flat():
    assert direction_correct("positive", 0.04) is True
    assert direction_correct("positive", -0.01) is False
    assert direction_correct("negative", -0.02) is True
    assert direction_correct("negative", 0.01) is False
    assert direction_correct("flat", 0.02) is True
    assert direction_correct("flat", 0.05) is False
    assert direction_correct("flat", -FLAT_BAND) is True
    assert direction_correct(None, 0.1) is None
    assert direction_correct("positive", None) is None


def test_watch_quality_is_not_yes_no():
    assert watch_decision_quality(None) == "pending"
    assert watch_decision_quality(0.01) == "muted_move"
    assert watch_decision_quality(0.08) == "missed_upside"
    assert watch_decision_quality(-0.08) == "missed_downside"


def test_chavda_horizons_pending_on_28_aug_2026():
    entry = date(2026, 8, 26)
    as_of = date(2026, 8, 28)
    assert horizon_elapsed(entry, 30, as_of) is False
    assert horizon_elapsed(entry, 365, as_of) is False
    metrics = compute_horizon_metrics(
        entry_price=138.05,
        entry_date=entry,
        horizon_days=30,
        stock=pd.DataFrame(),
        nifty=pd.DataFrame(),
        as_of=as_of,
    )
    assert metrics["status"] == "pending"
    assert metrics["absolute_return"] is None
    assert metrics["entry_price"] == 138.05


def test_elapsed_horizon_computes_returns_without_network():
    idx = pd.date_range("2026-08-26", periods=40, freq="B")
    close = pd.Series([138.05 + i * 0.5 for i in range(len(idx))], index=idx)
    stock = pd.DataFrame({
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": 10_000,
    })
    nifty = pd.DataFrame({
        "Close": pd.Series([25000 + i * 10 for i in range(len(idx))], index=idx),
    })
    metrics = compute_horizon_metrics(
        entry_price=138.05,
        entry_date=date(2026, 8, 26),
        horizon_days=30,
        stock=stock,
        nifty=nifty,
        as_of=date(2026, 10, 1),
    )
    assert metrics["status"] == "elapsed"
    assert metrics["exit_price"] is not None
    assert metrics["absolute_return"] > 0
    assert metrics["nifty_return"] is not None
    assert metrics["relative_return"] is not None
    assert direction_correct("positive", metrics["absolute_return"]) is True
    assert direction_correct("flat", metrics["absolute_return"]) is False
    assert watch_decision_quality(metrics["absolute_return"]) in {"missed_upside", "muted_move"}
