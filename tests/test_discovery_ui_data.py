"""Discovery UI data layer: episodes load without teaching agents."""
from agents.episode_store import list_discovery_council_episodes
from discovery_ui import _badge, _pct


def test_council_episodes_include_chavda_and_sample():
    rows = list_discovery_council_episodes()
    tickers = {r.get("ticker") for r in rows}
    assert "CHAVDA" in tickers
    types = {r.get("event_type") for r in rows}
    assert "large_order_win" in types
    assert "promoter_purchase" in types or "preferential_issue" in types


def test_badges_and_pending_pct():
    assert "WATCH" in _badge("watch")
    assert "BUY" in _badge("buy")
    assert _pct(None) == "pending"
    assert _pct(0.021).startswith("+")
