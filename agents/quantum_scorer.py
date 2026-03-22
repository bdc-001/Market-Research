"""
QuanTum Factor Scorer (v5) — Full Multi-Layer Model

Factors:
  1. VALUE           Earnings yield + inverse P/B (sector-adjusted)
  2. QUALITY         ROE + leverage + margin (financials corrected)
  3. MOMENTUM        Weighted period returns
  4. TECHNICAL       RSI + MACD + trend alignment
  5. VOLATILITY      Inverse 20d annualized vol
  6. SECTOR_GROWTH   Structural industry outlook (Year/5Yr)
  7. NEWS_CATALYST   Deep impact score: sentiment + surprise + event + reaction (Weekly)
  8. FLOW            Institutional accumulation: OBV slope + volume patterns
  9. EARNINGS_REV    Analyst estimate revisions + growth acceleration

Weights are dynamically set by the Market Regime Detector (BULL/BEAR/SIDEWAYS).
"""

import pandas as pd
import numpy as np


# ── Sector Classification ─────────────────────────────────────────────────────

SECTOR_MAP = {
    "HDFCBANK": "BFSI", "ICICIBANK": "BFSI", "SBIN": "BFSI",
    "KOTAKBANK": "BFSI", "AXISBANK": "BFSI", "PNB": "BFSI",
    "BANKBARODA": "BFSI", "CANBK": "BFSI", "FEDERALBNK": "BFSI",
    "IDFCFIRSTB": "BFSI", "BAJFINANCE": "BFSI", "BAJAJFINSV": "BFSI",
    "CHOLAFIN": "BFSI", "MUTHOOTFIN": "BFSI", "BAJAJHLDNG": "BFSI",
    "HDFCLIFE": "BFSI", "SHRIRAMFIN": "BFSI", "INDUSINDBK": "BFSI",
    "LICI": "BFSI",
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT",
    "TECHM": "IT", "PERSISTENT": "IT", "LTIM": "IT", "MPHASIS": "IT",
    "COFORGE": "IT",
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "DIVISLAB": "Pharma", "LUPIN": "Pharma", "TORNTPHARM": "Pharma",
    "AUROPHARMA": "Pharma", "GLAND": "Pharma", "ALKEM": "Pharma",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "GODREJCP": "FMCG", "TATACONSUM": "FMCG",
    "HAL": "Defence", "BEL": "Defence", "BHEL": "CapGoods",
    "ABB": "CapGoods", "SIEMENS": "CapGoods", "CUMMINSIND": "CapGoods",
    "THERMAX": "CapGoods", "GRINDWELL": "CapGoods", "BEML": "Defence",
    "LT": "CapGoods",
    "RELIANCE": "Energy", "TATAPOWER": "GreenEnergy", "POWERGRID": "Power",
    "NTPC": "Power", "ADANIGREEN": "GreenEnergy", "SJVN": "GreenEnergy",
    "NHPC": "GreenEnergy", "JSWENERGY": "GreenEnergy",
    "JSWSTEEL": "Metals", "HINDALCO": "Metals", "COALINDIA": "Metals",
    "MARUTI": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto",
    "EICHERMOT": "Auto", "HEROMOTOCO": "Auto",
    "BHARTIARTL": "Telecom",
    "DMART": "Retail", "TRENT": "Retail", "NYKAA": "Digital",
    "ETERNAL": "Digital", "PAYTM": "Digital", "TITAN": "Consumer",
    "ASIANPAINT": "Consumer", "PIDILITIND": "Consumer",
    "BERGEPAINT": "Consumer", "HAVELLS": "Consumer",
    "VOLTAS": "Consumer", "ULTRACEMCO": "Cement",
    "JUBLFOOD": "Consumer", "IRCTC": "Consumer",
    "DLF": "RealEstate", "GODREJPROP": "RealEstate",
    "PRESTIGE": "RealEstate", "OBEROIRLTY": "RealEstate",
    "GMRAIRPORT": "Infra", "ADANIENT": "Infra", "ADANIPORTS": "Infra",
}

FINANCIAL_SECTORS = {"BFSI"}

SECTOR_GROWTH_SCORES = {
    "Defence": 1.00, "GreenEnergy": 0.95, "Digital": 0.90,
    "CapGoods": 0.85, "Pharma": 0.80, "IT": 0.75, "Telecom": 0.75,
    "Auto": 0.70, "Retail": 0.65, "Consumer": 0.60, "Energy": 0.60,
    "Infra": 0.60, "BFSI": 0.55, "FMCG": 0.50, "Power": 0.50,
    "RealEstate": 0.45, "Cement": 0.45, "Metals": 0.35,
}

# Default weights (used when no regime data available)
DEFAULT_WEIGHTS = {
    "week": {
        "value": 0.00, "quality": 0.00, "momentum": 0.25,
        "technical": 0.30, "volatility": 0.10, "sector_growth": 0.00,
        "news_catalyst": 0.20, "flow": 0.10, "earnings_revision": 0.05,
    },
    "year": {
        "value": 0.10, "quality": 0.20, "momentum": 0.10,
        "technical": 0.05, "volatility": 0.05, "sector_growth": 0.15,
        "news_catalyst": 0.00, "flow": 0.15, "earnings_revision": 0.20,
    },
    "5years": {
        "value": 0.15, "quality": 0.25, "momentum": 0.05,
        "technical": 0.00, "volatility": 0.10, "sector_growth": 0.25,
        "news_catalyst": 0.00, "flow": 0.00, "earnings_revision": 0.20,
    },
}

TOP_PERCENTILE_THRESHOLD = 0.80


def _get_sector(ticker: str) -> str:
    return SECTOR_MAP.get(ticker, "Other")


def _is_financial(ticker: str) -> bool:
    return _get_sector(ticker) in FINANCIAL_SECTORS


def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="keep")


# ── Factor Computers ──────────────────────────────────────────────────────────

def compute_value_factor(df: pd.DataFrame) -> pd.Series:
    ey = df["earnings_yield"].copy().clip(lower=0)
    ey_rank = _pct_rank(ey)
    pb = df.get("pb_ratio", pd.Series(dtype=float))
    inv_pb = 1.0 / pb.where(pb > 0, np.nan)
    inv_pb_rank = _pct_rank(inv_pb)
    return (0.6 * ey_rank.fillna(0) + 0.4 * inv_pb_rank.fillna(0)) * 100


def compute_quality_factor(df: pd.DataFrame) -> pd.Series:
    is_fin = df["ticker"].apply(_is_financial)
    roe = df["roe"].copy()
    roe_pct = roe.where(roe > 1, roe * 100)
    roe_rank = _pct_rank(roe_pct).fillna(0)
    de = df["debt_equity"].copy()
    inv_de = 1.0 / (1.0 + de.where(de >= 0, np.nan))
    inv_de_rank = _pct_rank(inv_de).fillna(0)
    inv_de_rank = inv_de_rank.where(~is_fin, 0.50)
    pm = df.get("profit_margin", pd.Series(dtype=float))
    pm_rank = _pct_rank(pm).fillna(0)
    pm_rank = pm_rank.where(~is_fin, 0.50)
    score = pd.Series(0.0, index=df.index)
    score = score.where(is_fin, 0.45 * roe_rank + 0.30 * inv_de_rank + 0.25 * pm_rank)
    score = score.where(~is_fin, 0.70 * roe_rank + 0.15 * inv_de_rank + 0.15 * pm_rank)
    return score * 100


def compute_momentum_factor(df: pd.DataFrame, horizon: str) -> pd.Series:
    """
    Blended momentum: 60% sector-relative + 40% absolute.
    Sector-relative prevents false positives from weak-sector momentum.
    Absolute retains genuine broad-market outperformance signal.
    """
    r1_raw = df.get("return_1m", pd.Series(dtype=float, index=df.index))
    r3_raw = df.get("return_3m", pd.Series(dtype=float, index=df.index))
    r6_raw = df.get("return_6m", pd.Series(dtype=float, index=df.index))
    r12_raw = df.get("return_12m", pd.Series(dtype=float, index=df.index))

    sectors = df["ticker"].apply(_get_sector)

    # Sector-relative ranks
    r1_rel = _pct_rank(_sector_relative(r1_raw, sectors))
    r3_rel = _pct_rank(_sector_relative(r3_raw, sectors))
    r6_rel = _pct_rank(_sector_relative(r6_raw, sectors))
    r12_rel = _pct_rank(_sector_relative(r12_raw, sectors))

    # Absolute ranks
    r1_abs = _pct_rank(r1_raw)
    r3_abs = _pct_rank(r3_raw)
    r6_abs = _pct_rank(r6_raw)
    r12_abs = _pct_rank(r12_raw)

    # Blend: 60% relative + 40% absolute
    r1 = 0.60 * r1_rel.fillna(0) + 0.40 * r1_abs.fillna(0)
    r3 = 0.60 * r3_rel.fillna(0) + 0.40 * r3_abs.fillna(0)
    r6 = 0.60 * r6_rel.fillna(0) + 0.40 * r6_abs.fillna(0)
    r12 = 0.60 * r12_rel.fillna(0) + 0.40 * r12_abs.fillna(0)

    if horizon == "week":
        score = 0.50 * r1 + 0.30 * r3 + 0.20 * r6
    elif horizon == "year":
        score = 0.20 * r3 + 0.40 * r6 + 0.40 * r12
    else:
        score = 0.30 * r6 + 0.70 * r12
    return score * 100


def _sector_relative(returns: pd.Series, sectors: pd.Series) -> pd.Series:
    """Subtract sector mean from each stock's return to get relative strength."""
    if returns.isna().all():
        return returns
    combined = pd.DataFrame({"ret": returns, "sector": sectors})
    sector_mean = combined.groupby("sector")["ret"].transform("mean")
    return returns - sector_mean.fillna(0)


def compute_technical_factor(df: pd.DataFrame, horizon: str) -> pd.Series:
    results = []
    for _, row in df.iterrows():
        rsi = row.get("rsi", np.nan)
        macd = row.get("macd", np.nan)
        macd_sig = row.get("macd_signal", np.nan)
        close = row.get("close", np.nan)
        sma50 = row.get("sma50", np.nan)
        sma200 = row.get("sma200", np.nan)

        rsi_score = 0.0
        if not pd.isna(rsi):
            optimal = 50 if horizon in ("week", "5years") else 55
            sigma = 15 if horizon == "week" else 20
            rsi_score = np.exp(-((rsi - optimal) ** 2) / (2 * sigma ** 2))

        macd_score = 0.5
        if not pd.isna(macd) and not pd.isna(macd_sig):
            if macd > macd_sig and macd > 0:
                macd_score = 1.0
            elif macd > macd_sig:
                macd_score = 0.75
            elif abs(macd - macd_sig) < abs(macd_sig) * 0.1:
                macd_score = 0.5
            else:
                macd_score = 0.2

        trend_score = 0.5
        if not pd.isna(close):
            above_50 = (close > sma50) if not pd.isna(sma50) else False
            above_200 = (close > sma200) if not pd.isna(sma200) else False
            gc = (sma50 > sma200) if (not pd.isna(sma50) and not pd.isna(sma200)) else False
            if horizon == "week":
                trend_score = 0.8 if above_50 else 0.2
            else:
                if above_200 and gc:
                    trend_score = 1.0
                elif above_200:
                    trend_score = 0.7
                elif above_50:
                    trend_score = 0.4
                else:
                    trend_score = 0.1

        if horizon == "week":
            raw = 0.40 * rsi_score + 0.35 * macd_score + 0.25 * trend_score
        elif horizon == "year":
            raw = 0.25 * rsi_score + 0.30 * macd_score + 0.45 * trend_score
        else:
            raw = 0.15 * rsi_score + 0.15 * macd_score + 0.70 * trend_score
        results.append(raw)

    return _pct_rank(pd.Series(results, index=df.index)).fillna(0) * 100


def compute_volatility_factor(df: pd.DataFrame) -> pd.Series:
    vol = df.get("volatility_20d", pd.Series(dtype=float))
    inv_vol = 1.0 / vol.where(vol > 0, np.nan)
    return _pct_rank(inv_vol).fillna(0) * 100


def compute_sector_growth_factor(df: pd.DataFrame) -> pd.Series:
    scores = df["ticker"].apply(
        lambda t: SECTOR_GROWTH_SCORES.get(_get_sector(t), 0.50)
    )
    return scores * 100


def compute_news_catalyst_factor(df: pd.DataFrame, news_data: list[dict] | None) -> pd.Series:
    """
    Uses the deep impact score from NewsScanner v2.
    news_impact_score already combines sentiment, surprise, event_type, reaction.
    """
    if not news_data:
        return pd.Series(50.0, index=df.index)

    impact_map = {}
    for item in news_data:
        sym = item.get("symbol", "").upper()
        impact = item.get("news_impact_score")
        if impact is None:
            sent = float(item.get("sentiment", 0))
            urgency = {"high": 1.0, "medium": 0.7, "low": 0.4}.get(item.get("urgency", "medium"), 0.7)
            impact = (sent + 1) / 2.0 * urgency * 100
        impact_map[sym] = impact

    scores = df["ticker"].apply(lambda t: impact_map.get(t, 30.0))
    return _pct_rank(scores).fillna(0) * 100


# ── Main Scorer ───────────────────────────────────────────────────────────

class FactorScorer:

    def score(
        self,
        df: pd.DataFrame,
        horizon: str,
        news_data: list[dict] | None = None,
        flow_scores: pd.Series | None = None,
        earnings_scores: pd.Series | None = None,
        weights: dict | None = None,
    ) -> pd.DataFrame:
        """
        Score stocks with all 9 factors. Weights come from regime detector
        or fall back to DEFAULT_WEIGHTS.
        """
        w = weights or DEFAULT_WEIGHTS[horizon]
        out = df[["ticker", "close"]].copy()

        out["sector"] = df["ticker"].apply(_get_sector)
        out["value_score"] = compute_value_factor(df).values
        out["quality_score"] = compute_quality_factor(df).values
        out["momentum_score"] = compute_momentum_factor(df, horizon).values
        out["technical_score"] = compute_technical_factor(df, horizon).values
        out["volatility_score"] = compute_volatility_factor(df).values
        out["sector_growth_score"] = compute_sector_growth_factor(df).values
        out["news_catalyst_score"] = compute_news_catalyst_factor(df, news_data).values
        out["flow_score"] = flow_scores.values if flow_scores is not None else 50.0
        out["earnings_rev_score"] = earnings_scores.values if earnings_scores is not None else 50.0

        out["composite_score"] = (
            out["value_score"] * w.get("value", 0)
            + out["quality_score"] * w.get("quality", 0)
            + out["momentum_score"] * w.get("momentum", 0)
            + out["technical_score"] * w.get("technical", 0)
            + out["volatility_score"] * w.get("volatility", 0)
            + out["sector_growth_score"] * w.get("sector_growth", 0)
            + out["news_catalyst_score"] * w.get("news_catalyst", 0)
            + out["flow_score"] * w.get("flow", 0)
            + out["earnings_rev_score"] * w.get("earnings_revision", 0)
        ).round(1)

        # Factor agreement: count of active factors in top 20%
        if horizon == "week":
            active_cols = [c for c in ["news_catalyst_score", "technical_score",
                                        "momentum_score", "flow_score"]
                           if w.get(c.replace("_score", "").replace("news_catalyst_score", "news_catalyst"), 0) > 0]
            if not active_cols:
                active_cols = ["news_catalyst_score", "technical_score", "momentum_score"]
            max_agree = len(active_cols)
            out["factor_agreement"] = (
                out[active_cols].gt(TOP_PERCENTILE_THRESHOLD * 100).sum(axis=1)
            )
        else:
            all_factors = ["value_score", "quality_score", "momentum_score",
                           "technical_score", "volatility_score",
                           "flow_score", "earnings_rev_score"]
            active = [f for f in all_factors
                      if w.get(f.replace("_score", "").replace("earnings_rev_score", "earnings_revision"), 0) > 0]
            max_agree = len(active)
            out["factor_agreement"] = (
                out[active].gt(TOP_PERCENTILE_THRESHOLD * 100).sum(axis=1)
            )

        # Dynamic conviction based on how many factors are active
        def _conviction(agree, total):
            ratio = agree / total if total > 0 else 0
            if ratio >= 0.9:
                return "Very High"
            if ratio >= 0.7:
                return "High"
            if ratio >= 0.5:
                return "Moderate"
            if ratio >= 0.3:
                return "Low"
            return "Very Low"

        out["conviction"] = out["factor_agreement"].apply(lambda a: _conviction(a, max_agree))

        carry_cols = [
            "pe_ratio", "pb_ratio", "roe", "debt_equity", "profit_margin",
            "rsi", "sma50", "sma200", "macd", "macd_signal",
            "return_1m", "return_3m", "return_6m", "return_12m",
            "volatility_20d", "volume_ratio",
            "market_cap", "earnings_yield", "dividend_yield",
        ]
        for col in carry_cols:
            if col in df.columns:
                out[col] = df[col].values

        if news_data and horizon == "week":
            catalyst_map = {item["symbol"]: item.get("catalyst", "") for item in news_data}
            event_map = {item["symbol"]: item.get("event_type", "") for item in news_data}
            out["news_catalyst"] = out["ticker"].map(catalyst_map).fillna("")
            out["event_type"] = out["ticker"].map(event_map).fillna("")

        out["horizon"] = horizon
        return out.sort_values("composite_score", ascending=False).reset_index(drop=True)
