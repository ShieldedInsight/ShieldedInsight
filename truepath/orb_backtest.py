"""TruePath ORB backtest and tuner, fed by OpenBB.

Replays the rules of truepath/TruePath_ORB_v1.pine and TruePath_ORB_v2.pine on 5-minute bars,
grid-searches the main inputs on the first part of the data (in-sample), checks the winners on
the rest (out-of-sample), and scores each against prop-firm rules.

    python truepath/orb_backtest.py --version 2              # ES=F NQ=F MES=F MNQ=F via OpenBB/yfinance
    python truepath/orb_backtest.py --version 1 --symbols ES=F --account 100000
    python truepath/orb_backtest.py --csv bars.csv --symbols ES=F   # offline: date,open,high,low,close,volume

v1: enter at the close of the first bar that closes outside the 9:30-9:45 ET range.
v2: the breakout bar must confirm (volume >= X x the average opening-range bar, RSI past a
    threshold, close in the outer part of the bar); then either enter at its close ("close")
    or rest a limit order at the broken level for N bars and enter on the retest ("level").

Yahoo serves 5-minute bars for about the last 60 days only, so treat the result as a first
read, not a 1-year backtest. Confirm on TradingView's Strategy Tester before trading it.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import dataclass, asdict, replace
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Point value ($ per 1.00 move) and tick size.
SPECS = {
    "ES": (50.0, 0.25), "MES": (5.0, 0.25),
    "NQ": (20.0, 0.25), "MNQ": (2.0, 0.25),
    "GC": (100.0, 0.10), "MGC": (10.0, 0.10),
}
COMMISSION_RT = 3.10  # $1.55 per side
PROP = {50000: {"eod_limit": 2000.0}, 100000: {"eod_limit": 3000.0}}

OR_START, OR_END = time(9, 30), time(9, 45)
FLAT_AT = time(15, 55)


@dataclass(frozen=True)
class Params:
    entry_end: time = time(11, 30)
    stop_mode: str = "mid"        # mid | opposite | atr
    reward: float = 2.0
    vwap_filter: bool = True
    first_break_only: bool = True
    max_trades: int = 2
    atr_mult: float = 1.5
    max_risk_usd: float = 500.0
    daily_loss_usd: float = 1000.0
    allow_longs: bool = True
    allow_shorts: bool = True
    # v2 confirmation and order type (defaults = off, i.e. v1 behaviour)
    entry_mode: str = "close"     # close | level
    vol_mult: float = 0.0         # breakout-bar volume >= vol_mult x avg opening-range bar volume (0 = off)
    rsi_long: float = 0.0         # RSI(14) must be >= this for longs and <= 100 - this for shorts (0 = off)
    close_loc: float = 0.0        # close in the top (long) / bottom (short) share of the bar, e.g. 0.6 (0 = off)
    retest_bars: int = 6          # how long the level order rests before it is cancelled


V1 = Params()
# Matches the TruePath_ORB_v2.pine defaults.
V2 = Params(vwap_filter=False, first_break_only=False, entry_mode="level", vol_mult=0.0,
            rsi_long=60.0, close_loc=0.6, retest_bars=6, stop_mode="mid", atr_mult=1.0, reward=2.0)


# ══════════════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_openbb(symbol: str, start: str) -> pd.DataFrame:
    from openbb import obb  # imported here so --csv works without OpenBB installed

    res = obb.equity.price.historical(symbol, provider="yfinance", interval="5m", start_date=start)
    return normalize(res.to_df())


def load_csv(path: str) -> pd.DataFrame:
    return normalize(pd.read_csv(path, index_col=0))


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    # yfinance (via OpenBB) returns naive timestamps in exchange time, i.e. New York for CME futures.
    idx = idx.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT") if idx.tz is None else idx
    df.index = idx.tz_convert("America/New_York")
    df = df[df.index.notna()]  # the repeated 1-2 a.m. hour on the DST change has no single New York time
    return df.sort_index().dropna(subset=["open", "high", "low", "close"])


def spec_for(symbol: str) -> tuple[float, float]:
    root = symbol.upper().replace("=F", "").rstrip("0123456789!")
    if root not in SPECS:
        raise SystemExit(f"no contract spec for {symbol}; add it to SPECS")
    return SPECS[root]


def rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()  # Wilder's smoothing, as in ta.atr / ta.rsi


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    prev = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    delta = df["close"].diff()
    up, down = rma(delta.clip(lower=0), 14), rma(-delta.clip(upper=0), 14)
    rsi = 100 - 100 / (1 + up / down.replace(0, math.nan))
    return df.assign(atr=rma(tr, 14), rsi=rsi.fillna(100))


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

def round_tick(x: float, tick: float) -> float:
    return round(round(x / tick) * tick, 10)


def simulate(df: pd.DataFrame, p: Params, point_value: float, tick: float) -> list[dict]:
    """One contract. "close" entries fill at the signal bar's close; "level" entries are limit
    orders at the broken range edge that fill on a later bar (at the open if it gaps through).
    If a bar touches both stop and target, the stop is assumed first (conservative); a level
    order that fills on a bar that also reaches the stop counts as stopped on that bar."""
    trades: list[dict] = []
    if "atr" not in df:
        df = add_indicators(df)
    for day, d in df.groupby(df.index.date):
        t = d.index.time
        rng = d[(t >= OR_START) & (t < OR_END)]
        if len(rng) < 3:
            continue
        hi, lo = rng["high"].max(), rng["low"].min()
        mid = (hi + lo) / 2
        or_vol = rng["volume"].mean()
        sess = d[t >= OR_START]
        tp = (sess["high"] + sess["low"] + sess["close"]) / 3
        vwap = (tp * sess["volume"]).cumsum() / sess["volume"].cumsum().replace(0, math.nan)

        pos = pending = None
        day_pnl, n_trades, broke = 0.0, 0, False
        prev_close = rng["close"].iloc[-1]

        def close_out(px: float, why: str, now: time) -> None:
            nonlocal pos, day_pnl
            side, entry, stop, target, risk, t_in = pos
            pnl = (px - entry) * side * point_value - COMMISSION_RT
            day_pnl += pnl
            trades.append({"date": str(day), "side": "long" if side > 0 else "short", "entry_time": t_in,
                           "exit_time": now.strftime("%H:%M"), "entry": entry, "exit": px, "exit_reason": why,
                           "r": round((px - entry) * side / risk, 2), "pnl": round(pnl, 2)})
            pos = None

        after = sess[sess.index.time >= OR_END]
        for i, (ts, bar) in enumerate(after.iterrows()):
            now = ts.time()
            if pos:
                side, entry, stop, target, risk, _ = pos
                if (bar["low"] <= stop) if side > 0 else (bar["high"] >= stop):
                    close_out(stop, "stop", now)
                elif (bar["high"] >= target) if side > 0 else (bar["low"] <= target):
                    close_out(target, "target", now)
                elif now >= FLAT_AT:
                    close_out(bar["close"], "flat", now)
                elif day_pnl + (bar["close"] - entry) * side * point_value - COMMISSION_RT <= -p.daily_loss_usd:
                    close_out(bar["close"], "daily_limit", now)
                prev_close = bar["close"]
                continue

            if pending:
                side, level, stop, target, expires = pending
                if i > expires or now >= p.entry_end:
                    pending = None
                elif (bar["low"] <= level) if side > 0 else (bar["high"] >= level):
                    fill = min(bar["open"], level) if side > 0 else max(bar["open"], level)
                    risk = (fill - stop) * side
                    pending = None
                    if risk > 0:
                        pos = (side, fill, stop, target, risk, now.strftime("%H:%M"))
                        n_trades += 1
                        if (bar["low"] <= stop) if side > 0 else (bar["high"] >= stop):
                            close_out(stop, "stop", now)
                    prev_close = bar["close"]
                    continue

            can = (pending is None and now < p.entry_end and day_pnl > -p.daily_loss_usd
                   and n_trades < p.max_trades and (not p.first_break_only or not broke))
            long_b = bar["close"] > hi and prev_close <= hi
            short_b = bar["close"] < lo and prev_close >= lo
            if can and (long_b or short_b):
                broke = True
                side = 1 if long_b else -1
                if confirmed(bar, side, p, vwap[ts], or_vol):
                    level = hi if side > 0 else lo
                    ref = bar["close"] if p.entry_mode == "close" else level
                    if p.stop_mode == "mid":
                        stop = mid
                    elif p.stop_mode == "opposite":
                        stop = lo if side > 0 else hi
                    else:
                        stop = ref - side * bar["atr"] * p.atr_mult
                    stop = round_tick(stop, tick)
                    risk = (ref - stop) * side
                    if risk > tick and risk * point_value <= p.max_risk_usd:
                        target = round_tick(ref + side * risk * p.reward, tick)
                        if p.entry_mode == "close":
                            pos = (side, ref, stop, target, risk, now.strftime("%H:%M"))
                            n_trades += 1
                        else:
                            pending = (side, level, stop, target, i + p.retest_bars)
            prev_close = bar["close"]
    return trades


def confirmed(bar: pd.Series, side: int, p: Params, vwap: float, or_vol: float) -> bool:
    if not (p.allow_longs if side > 0 else p.allow_shorts):
        return False
    if p.vwap_filter and not math.isnan(vwap) and (bar["close"] - vwap) * side <= 0:
        return False
    if p.vol_mult and bar["volume"] < p.vol_mult * or_vol:
        return False
    if p.rsi_long and (bar["rsi"] < p.rsi_long if side > 0 else bar["rsi"] > 100 - p.rsi_long):
        return False
    if p.close_loc:
        span = bar["high"] - bar["low"]
        loc = (bar["close"] - bar["low"]) / span if span > 0 else 0.5
        if (loc if side > 0 else 1 - loc) < p.close_loc:
            return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# METRICS & PROP FIRM SCORE
# ══════════════════════════════════════════════════════════════════════════════

def metrics(trades: list[dict], account: int) -> dict:
    if not trades:
        return {"trades": 0}
    pnl = pd.Series([t["pnl"] for t in trades])
    days = pd.Series([t["pnl"] for t in trades], index=[t["date"] for t in trades]).groupby(level=0).sum()
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = pnl.cumsum()
    max_dd = float((equity.cummax().clip(lower=0) - equity).max())
    net = float(pnl.sum())
    eod = PROP[account]["eod_limit"]
    best_day_share = float(days.max() / net) if net > 0 else None
    pf = float(wins / losses) if losses > 0 else math.inf
    m = {
        "trades": len(trades), "days_traded": int(days.size), "net_pnl": round(net, 2),
        "profit_factor": round(pf, 2) if pf != math.inf else "inf",
        "win_rate": round(float((pnl > 0).mean()), 3), "avg_r": round(sum(t["r"] for t in trades) / len(trades), 2),
        "avg_trade": round(net / len(trades), 2), "max_drawdown": round(max_dd, 2),
        "worst_day": round(float(days.min()), 2), "best_day": round(float(days.max()), 2),
        "days_over_eod_limit": int((days <= -eod).sum()),
        "best_day_share_of_profit": round(best_day_share, 2) if best_day_share is not None else None,
    }
    m["prop_score"] = prop_score(m, eod)
    return m


def prop_score(m: dict, eod: float) -> dict:
    """0-100. Edge (PF), daily-loss safety, drawdown vs the EOD limit, consistency, sample size."""
    pf = m["profit_factor"] if m["profit_factor"] != "inf" else 3.0
    parts = {
        "edge": 30 * min(max((pf - 1.0) / 1.0, 0), 1),                       # full marks at PF >= 2.0
        "daily_loss": 25 * (1 if m["days_over_eod_limit"] == 0 else 0) * min(1, max(0, 1 + m["worst_day"] / eod)),
        "drawdown": 20 * max(0, 1 - m["max_drawdown"] / eod),
        "consistency": 15 * (0 if m["best_day_share_of_profit"] is None else max(0, min(1, (0.6 - m["best_day_share_of_profit"]) / 0.3))),
        "sample": 10 * min(1, m["trades"] / 40),
    }
    total = round(sum(parts.values()))
    verdict = ("strong" if total >= 75 else "workable" if total >= 55 else "weak") if pf > 1.5 else "fails PF > 1.5"
    return {"total": total, "verdict": verdict, **{k: round(v, 1) for k, v in parts.items()}}


# ══════════════════════════════════════════════════════════════════════════════
# TUNING
# ══════════════════════════════════════════════════════════════════════════════

GRIDS = {
    1: {
        "stop_mode": ["mid", "opposite", "atr"],
        "reward": [1.5, 2.0, 2.5, 3.0],
        "vwap_filter": [True, False],
        "entry_end": [time(10, 30), time(11, 30), time(13, 0)],
        "first_break_only": [True, False],
    },
    2: {
        "entry_mode": ["close", "level"],
        "vol_mult": [0.0, 0.8, 1.0, 1.3],
        "rsi_long": [0.0, 55.0, 60.0],
        "close_loc": [0.0, 0.6, 0.75],
        "stop_mode": ["mid", "atr"],
        "reward": [1.5, 2.0, 3.0],
    },
}


def tune(df: pd.DataFrame, pv: float, tick: float, account: int, split: float, base: Params, grid: dict) -> dict:
    days = sorted(set(df.index.date))
    cut = days[int(len(days) * split)]
    ins, oos = df[df.index.date < cut], df[df.index.date >= cut]
    rows = []
    for combo in itertools.product(*grid.values()):
        p = replace(base, **dict(zip(grid, combo)))
        m = metrics(simulate(ins, p, pv, tick), account)
        if m["trades"] >= 8:
            rows.append((p, m))
    rows.sort(key=lambda r: (r[1]["prop_score"]["total"], r[1]["net_pnl"]), reverse=True)
    top = [{"params": jsonable(p), "in_sample": m, "out_of_sample": metrics(simulate(oos, p, pv, tick), account)}
           for p, m in rows[:5]]
    return {"split_date": str(cut), "in_sample_days": sum(d < cut for d in days),
            "out_of_sample_days": sum(d >= cut for d in days), "combos_tested": len(rows), "top": top}


def jsonable(p: Params) -> dict:
    return {k: (v.strftime("%H:%M") if isinstance(v, time) else v) for k, v in asdict(p).items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", type=int, choices=[1, 2], default=2)
    ap.add_argument("--symbols", nargs="+", default=["ES=F", "NQ=F", "MES=F", "MNQ=F"])
    ap.add_argument("--start", default=(pd.Timestamp.now() - pd.Timedelta(days=58)).strftime("%Y-%m-%d"))
    ap.add_argument("--csv", help="offline bars for a single symbol instead of OpenBB")
    ap.add_argument("--account", type=int, choices=sorted(PROP), default=50000)
    ap.add_argument("--split", type=float, default=0.67, help="share of days used for in-sample tuning")
    ap.add_argument("--max-risk", type=float, default=500.0)
    ap.add_argument("--daily-loss", type=float, default=1000.0)
    ap.add_argument("--out")
    a = ap.parse_args()

    out = Path(a.out or ROOT / "trader" / ("truepath_orb_backtest.json" if a.version == 1 else f"truepath_orb_v{a.version}_backtest.json"))
    base = replace(V1 if a.version == 1 else V2, max_risk_usd=a.max_risk, daily_loss_usd=a.daily_loss)
    report = {"created_by": "truepath-orb-backtest", "strategy": f"TruePath_ORB_v{a.version}",
              "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "source": "csv" if a.csv else "openbb/yfinance", "interval": "5m", "account": a.account,
              "eod_limit": PROP[a.account]["eod_limit"], "commission_round_trip": COMMISSION_RT,
              "assumptions": ["1 contract", "close entries fill at the signal-bar close",
                              "level entries fill at the level, or the open if a bar gaps through it",
                              "stop wins if a bar hits stop and target", "no slippage", "flat by 15:55 ET"],
              "results": {}}
    for sym in a.symbols:
        df = load_csv(a.csv) if a.csv else load_openbb(sym, a.start)
        pv, tick = spec_for(sym)
        if df.empty:
            report["results"][sym] = {"error": "no bars returned"}
            continue
        df = add_indicators(df)
        default_m = metrics(simulate(df, base, pv, tick), a.account)
        report["results"][sym] = {
            "bars": len(df), "first": str(df.index[0]), "last": str(df.index[-1]),
            "defaults": {"params": jsonable(base), "metrics": default_m},
            "tuning": tune(df, pv, tick, a.account, a.split, base, GRIDS[a.version]),
        }
        s = default_m.get("prop_score", {})
        print(f"{sym}: {default_m.get('trades', 0)} trades, net ${default_m.get('net_pnl', 0)}, "
              f"PF {default_m.get('profit_factor', '-')}, prop score {s.get('total', '-')} ({s.get('verdict', '-')})")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
