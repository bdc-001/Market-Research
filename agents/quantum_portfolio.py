"""
QuanTum Portfolio Construction Layer

Converts raw ranked picks into an optimal portfolio allocation:
  1. Risk-adjusted score: composite_score / volatility
  2. Position sizing: Kelly-approximated weights from risk-adjusted scores
  3. Sector concentration caps: max 30% per sector, max 20% per stock
  4. Minimum diversification: at least 5 positions
  5. Cash buffer in high-risk regimes

Caps are re-applied after every redistribution. Leftover that cannot be
placed without breaking a cap stays as extra cash — never forced back
into the book by a final normalize step.

Output: DataFrame with position_weight (%) for each stock.
"""
import pandas as pd
import numpy as np


MAX_SINGLE_POSITION = 0.20   # 20% max per stock
MAX_SECTOR_EXPOSURE = 0.30   # 30% max per sector
MIN_POSITIONS = 5
CASH_RESERVE_BEAR = 0.10     # 10% cash in BEAR regime
CASH_RESERVE_SIDEWAYS = 0.05 # 5% cash in SIDEWAYS
CASH_RESERVE_BULL = 0.00     # fully invested in BULL
_EPS = 1e-9
# Display rounding can add ~0.05pp; treat only true breaches as violations.
_AUDIT_STOCK_PCT = 20.05
_AUDIT_SECTOR_PCT = 30.05


class PortfolioConstructor:
    """
    Takes scored picks and produces optimal portfolio weights
    with sector/position constraints.
    """

    def construct(
        self,
        scored: pd.DataFrame,
        regime: str = "SIDEWAYS",
        top_n: int = 10,
    ) -> pd.DataFrame:
        """
        Returns a DataFrame with columns:
          ticker, sector, composite_score, risk_adj_score,
          raw_weight, position_weight, position_weight_pct
        """
        if scored.empty:
            return scored

        top = scored.head(max(top_n, MIN_POSITIONS)).copy().reset_index(drop=True)

        vol = top["volatility_20d"] if "volatility_20d" in top.columns else pd.Series(0.3, index=top.index)
        vol = vol.fillna(0.3).clip(lower=0.05)
        top["risk_adj_score"] = top["composite_score"] / (vol * 100)

        ras = top["risk_adj_score"].clip(lower=0)
        if float(ras.sum()) <= 0:
            ras = pd.Series(1.0, index=top.index)
        top["raw_weight"] = ras / ras.sum()

        if "sector" not in top.columns:
            top["sector"] = "Other"
        top["sector"] = top["sector"].fillna("Other")

        cash_floor = {
            "BULL": CASH_RESERVE_BULL,
            "BEAR": CASH_RESERVE_BEAR,
            "SIDEWAYS": CASH_RESERVE_SIDEWAYS,
        }.get(regime, CASH_RESERVE_SIDEWAYS)
        investable = 1.0 - cash_floor

        desired = top["raw_weight"] * investable
        top["position_weight"] = _cap_and_redistribute(
            desired, top["sector"], investable, ras,
        )
        top["position_weight_pct"] = (top["position_weight"] * 100).round(1)

        cash = max(0.0, 1.0 - float(top["position_weight"].sum()))
        if cash > 1e-6:
            cash_row = pd.DataFrame([{
                "ticker": "CASH",
                "sector": "Cash",
                "composite_score": 0,
                "risk_adj_score": 0,
                "raw_weight": 0,
                "position_weight": cash,
                "position_weight_pct": round(cash * 100, 1),
            }])
            top = pd.concat([top, cash_row], ignore_index=True)

        return top

    def portfolio_summary(self, portfolio: pd.DataFrame) -> dict:
        """Summary stats for the constructed portfolio."""
        invested = portfolio[portfolio["ticker"] != "CASH"]
        cash_pct = portfolio[portfolio["ticker"] == "CASH"]["position_weight_pct"].sum()

        sector_dist = {}
        if "sector" in invested.columns and not invested.empty:
            sector_dist = invested.groupby("sector")["position_weight_pct"].sum().to_dict()

        avg_vol = invested["volatility_20d"].mean() if "volatility_20d" in invested.columns else None
        max_pos = invested["position_weight_pct"].max() if not invested.empty else 0

        return {
            "num_positions": len(invested),
            "cash_pct": cash_pct,
            "max_position_pct": max_pos,
            "sector_distribution": sector_dist,
            "avg_volatility": avg_vol,
            "total_invested_pct": round(100 - cash_pct, 1),
        }


def _cap_and_redistribute(
    desired: pd.Series,
    sectors: pd.Series,
    investable: float,
    preference: pd.Series,
) -> pd.Series:
    """Clip stock and sector caps, then fill leftover only into names with room."""
    w = desired.clip(lower=0).astype(float).copy()
    sectors = sectors.reindex(w.index).fillna("Other")
    preference = preference.reindex(w.index).fillna(0).clip(lower=0)
    if float(preference.sum()) <= 0:
        preference = pd.Series(1.0, index=w.index)

    for _ in range(40):
        w = w.clip(lower=0, upper=MAX_SINGLE_POSITION)
        for sector in sectors.unique():
            idx = w.index[sectors == sector]
            sw = float(w.loc[idx].sum())
            if sw > MAX_SECTOR_EXPOSURE + _EPS:
                w.loc[idx] = w.loc[idx] * (MAX_SECTOR_EXPOSURE / sw)
        w = w.clip(upper=MAX_SINGLE_POSITION)

        leftover = investable - float(w.sum())
        if leftover <= 1e-8:
            break

        room_stock = (MAX_SINGLE_POSITION - w).clip(lower=0)
        add = pd.Series(0.0, index=w.index)
        eligible = room_stock > 1e-10
        pref = preference.where(eligible, 0.0)
        if float(pref.sum()) <= 0:
            break
        add = leftover * (pref / pref.sum())
        add = add.clip(upper=room_stock)

        for sector in sectors.unique():
            idx = w.index[sectors == sector]
            remaining = max(0.0, MAX_SECTOR_EXPOSURE - float(w.loc[idx].sum()))
            if remaining <= _EPS:
                add.loc[idx] = 0.0
                continue
            proposed = float(add.loc[idx].sum())
            if proposed > remaining + _EPS:
                add.loc[idx] = add.loc[idx] * (remaining / proposed)

        if float(add.sum()) <= _EPS:
            break
        w = w + add

    return w.clip(lower=0, upper=MAX_SINGLE_POSITION)


def audit_constraints(portfolio: pd.DataFrame | None) -> dict:
    """
    Observation-only: did the constructed book obey its stated caps?
    Does not change weights. Used for episode snapshots.
    """
    empty = {
        "stock_cap_pct": MAX_SINGLE_POSITION * 100,
        "sector_cap_pct": MAX_SECTOR_EXPOSURE * 100,
        "max_position_pct": 0.0,
        "sector_weights": {},
        "violations": [],
        "weights": {},
    }
    if portfolio is None or getattr(portfolio, "empty", True):
        return empty

    invested = portfolio[portfolio["ticker"] != "CASH"].copy()
    if invested.empty:
        return empty

    weights = {
        str(r["ticker"]): float(r.get("position_weight_pct") or 0)
        for _, r in invested.iterrows()
    }
    sector_weights = {}
    if "sector" in invested.columns:
        sector_weights = {
            str(k): float(v)
            for k, v in invested.groupby("sector")["position_weight_pct"].sum().items()
        }

    max_pos = float(invested["position_weight_pct"].max())
    violations = []
    if max_pos > _AUDIT_STOCK_PCT:
        worst = invested.loc[invested["position_weight_pct"].idxmax()]
        violations.append({
            "type": "stock_cap",
            "ticker": str(worst.get("ticker")),
            "value": round(max_pos, 2),
            "cap": 20,
        })
    for sector, total in sector_weights.items():
        if total > _AUDIT_SECTOR_PCT:
            violations.append({
                "type": "sector_cap",
                "sector": sector,
                "value": round(total, 2),
                "cap": 30,
            })

    return {
        "stock_cap_pct": 20,
        "sector_cap_pct": 30,
        "max_position_pct": round(max_pos, 2),
        "sector_weights": {k: round(v, 2) for k, v in sector_weights.items()},
        "violations": violations,
        "weights": weights,
    }
