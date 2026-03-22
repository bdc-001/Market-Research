"""
QuanTum Portfolio Construction Layer

Converts raw ranked picks into an optimal portfolio allocation:
  1. Risk-adjusted score: composite_score / volatility
  2. Position sizing: Kelly-approximated weights from risk-adjusted scores
  3. Sector concentration caps: max 30% per sector, max 20% per stock
  4. Minimum diversification: at least 5 positions
  5. Cash buffer in high-risk regimes

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

        top = scored.head(max(top_n, MIN_POSITIONS)).copy()

        # Step 1: Risk-adjusted score = composite / volatility
        vol = top.get("volatility_20d", pd.Series(0.3, index=top.index))
        vol = vol.fillna(0.3).clip(lower=0.05)
        top["risk_adj_score"] = top["composite_score"] / (vol * 100)

        # Step 2: Raw weights proportional to risk-adjusted score
        total_ras = top["risk_adj_score"].sum()
        if total_ras > 0:
            top["raw_weight"] = top["risk_adj_score"] / total_ras
        else:
            top["raw_weight"] = 1.0 / len(top)

        # Step 3: Cash reserve based on regime
        cash = {
            "BULL": CASH_RESERVE_BULL,
            "BEAR": CASH_RESERVE_BEAR,
            "SIDEWAYS": CASH_RESERVE_SIDEWAYS,
        }.get(regime, CASH_RESERVE_SIDEWAYS)

        investable = 1.0 - cash

        # Step 4: Apply single-stock cap
        top["position_weight"] = (top["raw_weight"] * investable).clip(upper=MAX_SINGLE_POSITION)

        # Step 5: Apply sector cap — iteratively redistribute excess
        for _ in range(3):  # iterate to converge
            if "sector" not in top.columns:
                break
            sector_sums = top.groupby("sector")["position_weight"].sum()
            over_sectors = sector_sums[sector_sums > MAX_SECTOR_EXPOSURE]

            if over_sectors.empty:
                break

            for sector, total_w in over_sectors.items():
                excess = total_w - MAX_SECTOR_EXPOSURE
                mask = top["sector"] == sector
                n_in_sector = mask.sum()
                if n_in_sector > 0:
                    # Proportionally reduce within sector
                    sector_weights = top.loc[mask, "position_weight"]
                    reduction = sector_weights / sector_weights.sum() * excess
                    top.loc[mask, "position_weight"] -= reduction

        # Step 6: Normalize to investable amount
        current_total = top["position_weight"].sum()
        if current_total > 0 and abs(current_total - investable) > 0.01:
            top["position_weight"] = top["position_weight"] / current_total * investable

        top["position_weight"] = top["position_weight"].clip(lower=0)
        top["position_weight_pct"] = (top["position_weight"] * 100).round(1)

        # Add cash row
        if cash > 0:
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
        if "sector" in invested.columns:
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
