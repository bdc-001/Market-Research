"""Discovery Phase A.2 report: leads vs opportunity candidates. Not a fake scoreboard."""
from __future__ import annotations

from datetime import datetime


def generate_catalyst_report(cards: list[dict], meta: dict) -> str:
    candidates = [c for c in cards if c.get("stage") == "opportunity_candidate"]
    leads = [c for c in cards if c.get("stage") == "event_lead"]
    discarded = [c for c in cards if c.get("stage") == "discard_lead"]
    lines = [
        "# Discovery · Phase A.2 — Event leads vs opportunity candidates",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Run: `{meta.get('run_id')}`",
        "",
        "This run is a **lead finder with economic materiality**, not an opportunity "
        "scoreboard. The frozen 25/20/20/25/10 formula is stored but **not used to rank**. "
        "Unknown analyst coverage is not treated as scarcity.",
        "",
        "## Funnel",
        "",
        f"- Primary universe (SME + microcap): **{meta.get('universe_n', 0)}**",
        f"- Filings after gates: **{meta.get('gated_events', 0)}**",
        f"- LLM + PDF expansion: **{meta.get('llm_events', 0)}**",
        f"- Opportunity candidates (materiality 3–5): **{len(candidates)}**",
        f"- Event leads to investigate (materiality 2): **{len(leads)}**",
        f"- Discarded as non-catalysts (materiality 0–1): **{len(discarded)}**",
        f"- Evidence expansion reports: **{len(meta.get('expansion_reports') or [])}**",
        "",
        "Ranking key is **economic materiality (0–5)**, then whether the tape looks unaware.",
        "",
    ]
    if meta.get("empty_reason"):
        lines += [meta["empty_reason"], ""]

    if candidates:
        lines += ["## Opportunity candidates", ""]
        for i, card in enumerate(candidates, 1):
            lines.extend(_card(i, card, kind="candidate"))
    else:
        lines += [
            "## Opportunity candidates",
            "",
            "None. No filing established a meaningful change to company economics "
            "(order/revenue, capacity scale, or equivalent).",
            "",
        ]

    if leads:
        lines += ["## Event leads — investigate, not opportunities yet", ""]
        for i, card in enumerate(leads, 1):
            lines.extend(_card(i, card, kind="lead"))

    if discarded:
        lines += ["## Discarded (administrative / minor)", ""]
        for card in discarded:
            mat = card.get("materiality") or {}
            lines.append(
                f"- **{card.get('ticker')}** `{card.get('event_type')}` "
                f"materiality {mat.get('score')}/5 — {mat.get('reason')}"
            )
        lines.append("")

    lines += [
        "## What this is not",
        "",
        "- Not an opportunity score. Almost everything at 8.75 in A.1 was a frozen-weight artefact.",
        "- Not Phase B quality/inflection. Not Phase C Council.",
        "- Next action for a candidate is Evidence Expansion, then Council on that pack — not more scoring.",
        "- Council must answer: is this genuinely asymmetric, or is the catalyst misleading?",
        "",
    ]
    return "\n".join(lines)


def _card(rank: int, card: dict, kind: str) -> list[str]:
    mat = card.get("materiality") or {}
    aware = card.get("market_awareness") or {}
    impact = card.get("economic_impact") or {}
    iq = card.get("information_quality") or {}
    vs_rev = mat.get("order_to_revenue")
    vs_mcap = mat.get("order_to_market_cap")
    title = "Opportunity candidate" if kind == "candidate" else "Event lead"
    hidden = "yes — tape muted with participation and little news" if aware.get("hidden") else "no / unproven"
    exp = card.get("expansion") or {}
    next_step = (
        f"Evidence expansion `{exp.get('verdict')}` — {exp.get('report_path')}"
        if exp else
        ("Council-ready if filing + financials confirm scale" if kind == "candidate"
         else "Retrieve full filing / results / order book — not an opportunity yet")
    )
    lines = [
        f"### {rank}. {card.get('ticker')} — {title}",
        "",
        f"**Tier:** {card.get('tier') or 'unknown'} · **Materiality:** {mat.get('score')}/5 ({mat.get('status')})",
        f"**Why it matters economically:** {mat.get('reason')}",
        f"**Event:** {card.get('catalyst') or card.get('subject')}",
        f"**Event type:** `{card.get('event_type')}` · **Direction:** {mat.get('direction') or 'unknown'}",
        f"**Order / revenue:** {_pct(vs_rev)} · **Order / mcap:** {_pct(vs_mcap)}",
        f"**Economic impact:** revenue {impact.get('revenue')} · margin {impact.get('margin')} "
        f"· cash flow {impact.get('cash_flow')} · duration {impact.get('duration')}",
        f"**Analyst coverage:** {aware.get('analyst')}",
        f"**News mentions (RSS scan):** {aware.get('news_mentions', 0)}",
        f"**Abnormal return (5d |%|):** {_fmt(aware.get('abnormal_return'))}%",
        f"**Abnormal volume:** {_fmt(aware.get('abnormal_volume'))}×",
        f"**Tape:** {aware.get('tape')} · **Looks hidden:** {hidden}",
        f"**Filing retrieved:** {iq.get('full_filing_available')} · **Source verified:** {iq.get('source_verified')}",
        f"**Confidence:** {card.get('confidence')} · **Next:** {next_step}",
        f"**Source id:** `{card.get('source_id')}` · **Event date:** {card.get('event_date') or card.get('announced_at') or 'unknown'}",
        f"**Event id:** `{card.get('event_id') or (card.get('evidence') or {}).get('event_id') or 'n/a'}`",
        "",
        f"> Source text: {_quote(card)}",
        "",
    ]
    return lines


def _quote(card: dict) -> str:
    subject = card.get("subject") or card.get("source_text") or ""
    excerpt = (card.get("filing_text") or card.get("filing_excerpt") or "")[:400]
    if excerpt and excerpt.strip() not in subject:
        return f"{subject}\n{excerpt}"[:700]
    return str(subject)[:500]


def _pct(value) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if n != n:
        return "unknown"
    return f"{n:.0%}"


def _fmt(value) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if n != n:
        return "n/a"
    return f"{n:.1f}"
