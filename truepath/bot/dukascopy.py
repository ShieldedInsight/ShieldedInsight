"""Download free Dukascopy 1-minute history and build 5-minute bars in New York time.

    python truepath/bot/dukascopy.py --symbols USA500IDXUSD USATECHIDXUSD --start 2018-01-01
    python truepath/bot/dukascopy.py --import-csv usa500idxusd-m1-bid-2018-01-01-2026-11-26.csv USA500IDXUSD

Note: from this cloud session Dukascopy rate-limits to ~3 files/minute and then stops answering, so
for multi-year history run dukascopy-node on your own computer and import the CSV.

Each UTC day is one LZMA file of 24-byte records: seconds from midnight, open, close, low, high
(int32, price x 1000 for index CFDs and gold) and tick volume (float32). BID side. Days are cached
under trader/data/duka_cache/ so a stopped run resumes. Output: trader/data/duka_<SYMBOL>_5m.csv.
Dukascopy rate-limits: 1 worker, a short pause per request, a browser user agent, backoff on HTTP 429.
"""

from __future__ import annotations

import argparse
import lzma
import struct
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "trader" / "data"
CACHE = DATA / "duka_cache"
URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y:04d}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"
PAUSE = 0.35  # seconds between requests per worker
SCALE = {"USA500IDXUSD": 1000, "USATECHIDXUSD": 1000, "USSC2000IDXUSD": 1000, "XAUUSD": 1000}


def fetch_day(sym: str, day: date) -> Path | None:
    out = CACHE / sym / f"{day:%Y%m%d}.bi5"
    if out.exists():
        return out
    url = URL.format(sym=sym, y=day.year, m=day.month - 1, d=day.day)   # months are 0-based
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(10):
        try:
            time.sleep(PAUSE)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            return out
        except urllib.error.HTTPError as e:
            if e.code == 404:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"")
                return out
            time.sleep(min(60, 10 * (attempt + 1)) if e.code == 429 else 2)
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def decode(path: Path, day: date, scale: int) -> pd.DataFrame:
    raw = path.read_bytes()
    if not raw:
        return pd.DataFrame()
    b = lzma.decompress(raw)
    a = np.frombuffer(b, dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"), ("h", ">i4"), ("v", ">f4")]))
    ts = pd.Timestamp(day, tz="UTC") + pd.to_timedelta(a["t"].astype(np.int64), unit="s")
    df = pd.DataFrame({"open": a["o"] / scale, "high": a["h"] / scale, "low": a["l"] / scale,
                       "close": a["c"] / scale, "volume": a["v"].astype(float)}, index=ts)
    return df[df["volume"] > 0]


def build(sym: str, start: date, end: date, workers: int = 1) -> Path:
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() != 5]            # no trading on Saturdays (UTC)
    t0, done = time.time(), 0
    with ThreadPoolExecutor(workers) as ex:
        paths = []
        for p in ex.map(lambda d: fetch_day(sym, d), days):
            paths.append(p)
            done += 1
            if done % 250 == 0:
                print(f"{sym}: {done}/{len(days)} days ({time.time() - t0:.0f}s)", flush=True)
    missing = [d for d, p in zip(days, paths) if p is None]
    frames = [decode(p, d, SCALE.get(sym, 1000)) for d, p in zip(days, paths) if p is not None]
    m1 = pd.concat([f for f in frames if len(f)]).sort_index()
    m1 = m1[~m1.index.duplicated()]
    m1.index = m1.index.tz_convert("America/New_York")
    m5 = m1.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
    out = DATA / f"duka_{sym}_5m.csv"
    m5.to_csv(out)
    print(f"{sym}: {len(m1):,} 1m bars -> {len(m5):,} 5m bars, {m5.index[0]} .. {m5.index[-1]}; missing days: {len(missing)}", flush=True)
    return out


def import_csv(path: str, sym: str) -> Path:
    """Convert a dukascopy-node CSV (timestamp in ms UTC, open, high, low, close, volume; m1 or m5)
    into trader/data/duka_<SYM>_5m.csv."""
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    df = df.set_index(ts)[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[df["volume"] > 0].sort_index()
    m5 = df.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
    out = DATA / f"duka_{sym}_5m.csv"
    m5.to_csv(out)
    print(f"{sym}: {len(m5):,} 5m bars, {m5.index[0]} .. {m5.index[-1]} -> {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--import-csv", nargs=2, metavar=("CSV", "SYMBOL"), help="convert a dukascopy-node download instead of fetching")
    ap.add_argument("--symbols", nargs="+", default=["USA500IDXUSD", "USATECHIDXUSD"])
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=(date.today() - timedelta(1)).isoformat())
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    if a.import_csv:
        import_csv(*a.import_csv)
        return
    for s in a.symbols:
        build(s, date.fromisoformat(a.start), date.fromisoformat(a.end), a.workers)


if __name__ == "__main__":
    main()
