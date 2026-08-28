"""
Pick a diverse Discovery sample for Council.

Does not change frozen scores. Does not teach agents.
CHAVDA is excluded — one episode is not a general rule.
"""
from __future__ import annotations

CHAVDA_TICKER = "CHAVDA"
CHAVDA_EVENT_ID = "ev_2522b5ccc6"

SAMPLE_EVENT_TYPES = (
    "large_order_win",
    "export_order",
    "promoter_purchase",
    "promoter_sale",
    "capacity_expansion",
    "new_customer",
    "fund_raise",
    "preferential_issue",
    "regulatory_approval",
    "new_product",
    "debt_reduction",
    "acquisition",
    "partnership",
    "divestiture",
)

_STAGE_RANK = {
    "opportunity_candidate": 3,
    "event_lead": 2,
    "discard_lead": 1,
}


def pick_sample_cards(
    cards: list[dict] | None,
    *,
    skip_tickers: set[str] | None = None,
    skip_event_ids: set[str] | None = None,
    max_n: int = 8,
    max_per_type: int = 2,
    allow_discarded: bool = True,
) -> list[dict]:
    """
    One diverse slice of the current radar. Prefers opportunity candidates and
    event leads. Optionally includes one discarded row per rare type so the
    sample is not only order-wins.
    """
    skip_tickers = {t.upper() for t in (skip_tickers or set())}
    skip_tickers.add(CHAVDA_TICKER)
    skip_event_ids = set(skip_event_ids or set())
    skip_event_ids.add(CHAVDA_EVENT_ID)

    eligible = []
    for card in cards or []:
        ticker = str(card.get("ticker") or "").upper()
        event_id = str(card.get("event_id") or (card.get("evidence") or {}).get("event_id") or "")
        stage = card.get("stage")
        event_type = card.get("event_type") or "unclassified"
        if ticker in skip_tickers or event_id in skip_event_ids:
            continue
        if stage == "discard_lead" and not allow_discarded:
            continue
        if stage == "discard_lead" and event_type not in SAMPLE_EVENT_TYPES:
            continue
        if stage not in _STAGE_RANK:
            continue
        eligible.append(card)

    eligible.sort(key=_sample_rank, reverse=True)

    picked: list[dict] = []
    per_type: dict[str, int] = {}
    seen_ticker: set[str] = set()
    for card in eligible:
        if len(picked) >= max_n:
            break
        ticker = str(card.get("ticker") or "").upper()
        event_type = card.get("event_type") or "unclassified"
        if ticker in seen_ticker:
            continue
        if per_type.get(event_type, 0) >= max_per_type:
            continue
        picked.append(card)
        seen_ticker.add(ticker)
        per_type[event_type] = per_type.get(event_type, 0) + 1
    return picked


def _sample_rank(card: dict) -> tuple:
    stage = card.get("stage")
    event_type = card.get("event_type") or ""
    mat = (card.get("materiality") or {}).get("score") or 0
    filing = 1 if (card.get("full_filing_available") or card.get("filing_text")) else 0
    type_bonus = 1 if event_type in SAMPLE_EVENT_TYPES else 0
    rare = 1 if event_type not in {"large_order_win", "financial_results", "management_change"} else 0
    return (_STAGE_RANK.get(stage, 0), type_bonus, rare, filing, mat)


def type_counts(cards: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for card in cards:
        key = card.get("event_type") or "unclassified"
        out[key] = out.get(key, 0) + 1
    return out
