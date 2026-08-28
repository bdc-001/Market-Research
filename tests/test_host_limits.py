"""Memory-capped host flags. Does not change frozen Discovery scores."""
from __future__ import annotations

import os

from agents.host_limits import constrained_host


def test_constrained_host_reads_low_memory_flag(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)
    monkeypatch.setenv("LOW_MEMORY", "1")
    assert constrained_host() is True
    monkeypatch.setenv("LOW_MEMORY", "0")
    assert constrained_host() is False


def test_sample_config_caps_llm_on_constrained_host(monkeypatch):
    monkeypatch.setenv("LOW_MEMORY", "1")
    from build_discovery_sample import sample_config

    cfg = sample_config(lookback_days=7, max_events_to_llm=40)
    assert cfg["radar"]["max_events_to_llm"] == 8
    assert cfg["radar"]["max_raw_announcements"] <= 120
