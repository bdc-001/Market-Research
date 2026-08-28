"""Load frozen Discovery config. Never written by a learning loop."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "discovery.yaml"

_FROZEN_WEIGHT_KEYS = (
    "catalyst", "scarcity", "quality", "inflection", "mispricing",
)


def load_discovery_config(path: Path | None = None) -> dict:
    target = Path(path) if path else CONFIG_PATH
    with target.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return _validate(data)


def _validate(raw: dict) -> dict:
    cfg = deepcopy(raw)
    score = cfg.setdefault("opportunity_score", {})
    score["frozen"] = True
    weights = score.setdefault("weights", {})
    for key in _FROZEN_WEIGHT_KEYS:
        weights.setdefault(key, 0.0)
        weights[key] = float(weights[key])
    total = sum(weights[k] for k in _FROZEN_WEIGHT_KEYS)
    if abs(total - 1.0) > 0.001:
        raise ValueError(
            f"Frozen opportunity weights must sum to 1.0, got {total:.4f}"
        )
    universe = cfg.setdefault("universe", {})
    universe.setdefault("mcap_min_cr", 50)
    universe.setdefault("microcap_max_cr", 1000)
    universe.setdefault("smallcap_max_cr", 5000)
    universe.setdefault("mcap_max_cr", universe.get("smallcap_max_cr", 5000))
    universe.setdefault("min_adv_inr", 5_000_000)
    universe.setdefault("indices", ["NIFTY MICROCAP 250"])
    universe.setdefault("primary_tiers", ["sme", "microcap"])
    universe.setdefault("include_smallcap", False)
    liq = cfg.setdefault("liquidity", {})
    liq["hard_gate"] = True
    liq.setdefault("unknown_is_exclude", True)
    return cfg


def frozen_weights(cfg: dict | None = None) -> dict[str, float]:
    cfg = cfg or load_discovery_config()
    weights = cfg["opportunity_score"]["weights"]
    return {k: float(weights[k]) for k in _FROZEN_WEIGHT_KEYS}
