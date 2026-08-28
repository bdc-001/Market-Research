"""
Keep the Render 512 MB web process from dying.

Discovery's Yahoo ADV pull for the whole SME universe, plus concurrent
council threads, is what trips the memory limit. Frozen scores are unchanged.
"""
from __future__ import annotations

import gc
import os


def constrained_host() -> bool:
    if os.environ.get("LOW_MEMORY", "").strip().lower() in {"1", "true", "yes"}:
        return True
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))


def adv_batch_size() -> int:
    return 20 if constrained_host() else 40


def yfinance_threads() -> bool:
    return not constrained_host()


def rss_mb() -> float | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except Exception:
        return None
    return None


def release_memory() -> None:
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
