"""
NSE / BSE HTTP client with disk cache.

Exchange pages need a browser-like session. Failures return empty
payloads so Discovery can degrade to news-only instead of crashing.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache" / "discovery"

NSE_HOME = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

BSE_HEADERS = {
    "User-Agent": NSE_HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


class ExchangeClient:
    def __init__(self, cache_ttl_minutes: int = 180, timeout: int = 20):
        self.timeout = timeout
        self.cache_ttl = timedelta(minutes=int(cache_ttl_minutes))
        self.session = requests.Session()
        self.session.headers.update(NSE_HEADERS)
        self._nse_ready = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{digest}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age > self.cache_ttl:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, key: str, payload: Any) -> None:
        try:
            self._cache_path(key).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            logger.debug("cache write skipped: %s", exc)

    def _warmup_nse(self) -> None:
        if self._nse_ready:
            return
        try:
            self.session.get(NSE_HOME, timeout=self.timeout)
            self.session.get(
                f"{NSE_HOME}/market-data/live-equity-market",
                timeout=self.timeout,
            )
            self._nse_ready = True
        except Exception as exc:
            logger.warning("NSE warmup failed: %s", exc)

    def nse_json(self, url: str, cache_key: str | None = None) -> Any:
        key = cache_key or url
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        self._warmup_nse()
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning("NSE %s -> %s", url, resp.status_code)
                return None
            payload = resp.json()
            self._write_cache(key, payload)
            time.sleep(0.35)
            return payload
        except Exception as exc:
            logger.warning("NSE fetch failed %s: %s", url, exc)
            return None

    def index_constituents(self, index_name: str) -> list[dict]:
        encoded = quote(index_name, safe="")
        # Hitting the live page first reduces 404s on the JSON API.
        self._warmup_nse()
        try:
            self.session.get(
                f"{NSE_HOME}/market-data/live-equity-market?symbol={encoded}",
                timeout=self.timeout,
            )
        except Exception:
            pass
        url = f"{NSE_HOME}/api/equity-stockIndices?index={encoded}"
        payload = self.nse_json(url, cache_key=f"index:{index_name}")
        rows = []
        if isinstance(payload, dict):
            rows = payload.get("data") or []
        if not rows:
            return self._niftyindices_csv(index_name)
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol or symbol in {"NIFTY", "INDIA VIX"}:
                continue
            if symbol.startswith("NIFTY"):
                continue
            out.append({
                "ticker": symbol,
                "exchange": "NSE",
                "source": index_name,
                "company_name": (
                    (row.get("meta") or {}).get("companyName")
                    or row.get("identifier")
                    or symbol
                ),
                "last_price": _num(row.get("lastPrice")),
                "turnover_inr": _num(row.get("totalTradedValue")),
                "volume": _num(row.get("totalTradedVolume")),
                "mcap_cr": _mcap_cr(row.get("ffmc") or row.get("marketCap")),
                "raw": {
                    "pChange": row.get("pChange"),
                    "ffmc": row.get("ffmc"),
                },
            })
        return out

    def _niftyindices_csv(self, index_name: str) -> list[dict]:
        """Public constituent CSVs when the NSE live index API 404s."""
        urls = {
            "NIFTY MICROCAP 250": (
                "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250list.csv"
            ),
            "NIFTY SMALLCAP 250": (
                "https://www.niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv"
            ),
        }
        url = urls.get(index_name)
        if not url:
            return []
        cached = self._read_cache(f"csv:{index_name}")
        if cached is None:
            try:
                resp = requests.get(url, headers=NSE_HEADERS, timeout=self.timeout)
                if resp.status_code != 200 or len(resp.content) < 200:
                    logger.warning("niftyindices %s -> %s", index_name, resp.status_code)
                    return []
                cached = {"csv": resp.text}
                self._write_cache(f"csv:{index_name}", cached)
            except Exception as exc:
                logger.warning("niftyindices %s failed: %s", index_name, exc)
                return []
        text = cached.get("csv") if isinstance(cached, dict) else None
        if not text:
            return []
        import csv
        from io import StringIO
        reader = csv.DictReader(StringIO(text))
        out = []
        for row in reader:
            symbol = str(row.get("Symbol") or row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            out.append({
                "ticker": symbol,
                "exchange": "NSE",
                "source": index_name,
                "company_name": str(row.get("Company Name") or row.get("Company") or symbol),
                "last_price": None,
                "turnover_inr": None,
                "volume": None,
                "mcap_cr": None,
                "raw": {},
            })
        return out

    def nse_sme_constituents(self) -> list[dict]:
        # Emerge live market; endpoint names have changed over time.
        urls = [
            f"{NSE_HOME}/api/live-analysis-emerge",
            f"{NSE_HOME}/api/equity-stockIndices?index={quote('NIFTY SME EMERGE', safe='')}",
            f"{NSE_HOME}/api/emerge-historical",
        ]
        for url in urls:
            payload = self.nse_json(url, cache_key=f"sme:{url}")
            rows = _rows_from_payload(payload)
            if not rows:
                continue
            out = []
            for row in rows:
                symbol = str(
                    row.get("symbol") or row.get("sm_symbol") or row.get("SYMBOL") or ""
                ).strip().upper()
                if not symbol:
                    continue
                out.append({
                    "ticker": symbol,
                    "exchange": "NSE_SME",
                    "source": "NSE SME/Emerge",
                    "company_name": str(
                        row.get("meta", {}).get("companyName")
                        if isinstance(row.get("meta"), dict)
                        else row.get("companyName") or row.get("name") or symbol
                    ),
                    "last_price": _num(row.get("lastPrice") or row.get("ltp")),
                    "turnover_inr": _num(
                        row.get("totalTradedValue") or row.get("turnover")
                    ),
                    "volume": _num(row.get("totalTradedVolume") or row.get("volume")),
                    "mcap_cr": _mcap_cr(row.get("ffmc") or row.get("marketCap")),
                    "raw": {},
                })
            if out:
                return out
        return []

    def nse_announcements(
        self,
        *,
        index: str,
        lookback_days: int,
        limit: int,
    ) -> list[dict]:
        """
        index: equities | sme
        """
        today = date.today()
        start = today - timedelta(days=int(lookback_days))
        from_s = start.strftime("%d-%m-%Y")
        to_s = today.strftime("%d-%m-%Y")
        urls = [
            (
                f"{NSE_HOME}/api/corporate-announcements?index={index}"
                f"&from_date={from_s}&to_date={to_s}"
            ),
            f"{NSE_HOME}/api/corporate-announcements?index={index}",
            (
                f"{NSE_HOME}/api/corporates-announcements?index={index}"
                f"&from_date={from_s}&to_date={to_s}"
            ),
        ]
        for url in urls:
            payload = self.nse_json(url, cache_key=f"ann:{index}:{from_s}:{to_s}:{url}")
            rows = _rows_from_payload(payload)
            if not rows:
                continue
            out = []
            for row in rows[: int(limit)]:
                if not isinstance(row, dict):
                    continue
                symbol = str(
                    row.get("symbol")
                    or row.get("sm_name")
                    or row.get("SYMBOL")
                    or ""
                ).strip().upper()
                subject = announcement_subject(row)
                if not symbol and not subject:
                    continue
                out.append({
                    "source": f"NSE:{index}",
                    "ticker": symbol,
                    "company_name": str(row.get("sm_name") or row.get("companyName") or symbol),
                    "subject": subject,
                    "announced_at": str(
                        row.get("an_dt") or row.get("sort_date") or row.get("datetime") or ""
                    ),
                    "attachment": str(
                        row.get("attchmntFile") or row.get("fileUrl") or ""
                    ),
                    "raw": {k: row.get(k) for k in list(row)[:12]},
                })
            if out:
                return out
        return []

    def bse_announcements(self, *, lookback_days: int, limit: int) -> list[dict]:
        today = date.today()
        start = today - timedelta(days=int(lookback_days))
        url = (
            "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
            f"?strCat=-1&strPrevDate={start.strftime('%Y%m%d')}"
            f"&strScrip=&strSearch=P&strToDate={today.strftime('%Y%m%d')}&strType=C"
        )
        cached = self._read_cache(url)
        if cached is None:
            try:
                resp = requests.get(url, headers=BSE_HEADERS, timeout=self.timeout)
                if resp.status_code != 200:
                    logger.warning("BSE announcements -> %s", resp.status_code)
                    cached = {}
                else:
                    cached = resp.json()
                    self._write_cache(url, cached)
            except Exception as exc:
                logger.warning("BSE announcements failed: %s", exc)
                cached = {}
        table = []
        if isinstance(cached, dict):
            table = cached.get("Table") or cached.get("data") or []
        out = []
        for row in table[: int(limit)]:
            if not isinstance(row, dict):
                continue
            subject = str(row.get("HEADLINE") or row.get("NEWS_SUB") or "")
            name = str(row.get("SLONGNAME") or row.get("SCRIP_CD") or "")
            ticker = str(row.get("SLONGNAME") or "").strip().upper()
            # BSE often gives company name, not NSE ticker. Keep name for matching.
            out.append({
                "source": "BSE",
                "ticker": "",
                "company_name": name,
                "subject": subject,
                "announced_at": str(row.get("NEWS_DT") or row.get("DissemDT") or ""),
                "attachment": str(row.get("ATTACHMENTNAME") or ""),
                "raw": {"scrip": row.get("SCRIP_CD"), "category": row.get("CATEGORYNAME")},
            })
        return out


def announcement_subject(row: dict) -> str:
    """Prefer the disclosure text over the NSE category label."""
    category = str(row.get("desc") or row.get("subject") or "").strip()
    detail = str(row.get("attchmntText") or row.get("headline") or "").strip()
    return " | ".join(p for p in (category, detail) if p)


def _rows_from_payload(payload: Any) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "Table", "announcements", "records"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                return val
        # Some NSE SME payloads nest once more.
        for val in payload.values():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val
    return []


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _mcap_cr(value) -> float | None:
    """Normalise NSE market-cap fields to crores."""
    n = _num(value)
    if n is None or n <= 0:
        return None
    if n > 1_000_000_000:      # rupees
        return n / 1e7
    if n > 100_000:            # lakhs
        return n / 100.0
    return n
