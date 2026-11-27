"""TruePath VWAP mean-reversion: backtest on long 5-minute history (Dukascopy) with a fixed test plan.

Model (RTH, 5-minute bars, New York time):
    VWAP_t  = sum(tp*v)/sum(v) since 09:30            tp = (high+low+close)/3
    sigma_t = sqrt(sum(v*(tp-VWAP)^2)/sum(v))         volume-weighted VWAP band width
    z_t     = (close_t - VWAP_t) / sigma_t
    enter   : z <= -k  -> long,  z >= +k -> short     (signal at the close, fill at the next open)
    edge    : |close - VWAP| >= 3 x round-trip cost (points)
    exits   : VWAP touch (target) | stop 1.5 sigma beyond entry | 24 bars | 15:55 flat
    limits  : entries 10:00-15:00, max 2 per side per day, stop after 2 losing trades

Filters (switches; values fixed before any run):
    F1 trend_veto   session efficiency ratio |close - open_0930| / sum|dclose| <= 0.5
    F2 regime       variance ratio of 5m returns (q=6) over the prior 20 sessions < 1
    F3 reversal_bar the bar after the stretch must turn (up close for longs, down for shorts)
    F4 location     the stretch reached the prior session's low (longs) / high (shorts) or beyond
    F5 htf_align    longs only above the 20-day average close, shorts only below
    F6 midday       entries only 10:30-14:30
    F7 vol_band     daily ATR(14) between its 20th and 80th percentile over the prior 250 days

Plan: train 2018-2022, test 2023-2026 (judged once). k in {2.0, 2.5, 3.0} chosen by train t-stat;
filters added one at a time on train, kept only if they raise BOTH profit factor and t-stat.

    python truepath/bot/vwap_revert.py            # Dukascopy long history
    python truepath/bot/vwap_revert.py --yahoo    # 60 days of ES/NQ futures, to check the code only
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "trader" / "data"
MARKETS = {  # Dukascopy symbol -> (micro, $/point, tick)
    "USA500IDXUSD": ("MES", 5.0, 0.25),
    "USATECHIDXUSD": ("MNQ", 2.0, 0.25),
}
COMMISSION_SIDE, SLIP_TICKS = 1.55, 2
TRAIN_END = pd.Timestamp("2023-01-01", tz="America/New_York")


@dataclass(frozen=True)
class P:
    k: float = 2.5
    stop_sigma: float = 1.5
    max_bars: int = 24
    edge_mult: float = 3.0
    start: str = "10:00"
    end: str = "15:00"
    trend_veto: bool = False
    regime: bool = False
    reversal_bar: bool = False
    location: bool = False
    htf_align: bool = False
    midday: bool = False
    vol_band: bool = False


SOURCE = {"name": "duka"}   # "duka": trader/data/duka_<SYM>_5m.csv; "yahoo": ES_5m / NQ_5m futures (60 days, for debugging)
YAHOO = {"USA500IDXUSD": "ES", "USATECHIDXUSD": "NQ"}


def data_path(sym: str) -> Path:
    return DATA / (f"{YAHOO[sym]}_5m.csv" if SOURCE["name"] == "yahoo" else f"duka_{sym}_5m.csv")


def load(sym: str) -> pd.DataFrame:
    df = pd.read_csv(data_path(sym), index_col=0)
    idx = pd.to_datetime(df.index)
    if idx.tz is None:      # yfinance: naive New York time
        idx = idx.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    df.index = pd.to_datetime(idx, utc=True).tz_convert("America/New_York")
    return df[df.index.notna()][["open", "high", "low", "close", "volume"]].astype(float)


def session_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """RTH bars with VWAP, sigma, z, efficiency ratio; plus a daily table for the slower filters."""
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["day"] = rth.index.normalize()
    tp = (rth["high"] + rth["low"] + rth["close"]) / 3
    v = rth["volume"].clip(lower=1e-9)
    g = rth.groupby("day")
    cv = v.groupby(rth["day"]).cumsum()
    vwap = (tp * v).groupby(rth["day"]).cumsum() / cv
    var = ((v * tp ** 2).groupby(rth["day"]).cumsum() / cv) - vwap ** 2
    rth["vwap"], rth["sigma"] = vwap, np.sqrt(var.clip(lower=0))
    rth["z"] = (rth["close"] - rth["vwap"]) / rth["sigma"].replace(0, np.nan)
    o0 = g["open"].transform("first")
    path = rth["close"].diff().abs().where(rth["day"] == rth["day"].shift(), 0).groupby(rth["day"]).cumsum()
    rth["er"] = (rth["close"] - o0).abs() / path.replace(0, np.nan)

    daily = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()})
    prev_c = daily["close"].shift()
    tr = pd.concat([daily["high"] - daily["low"], (daily["high"] - prev_c).abs(), (daily["low"] - prev_c).abs()], axis=1).max(1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    daily["atr"] = atr.shift()                       # known at the open: through the prior session
    daily["atr_lo"] = daily["atr"].rolling(250, min_periods=120).quantile(0.2)
    daily["atr_hi"] = daily["atr"].rolling(250, min_periods=120).quantile(0.8)
    daily["sma20"] = daily["close"].rolling(20).mean().shift()
    daily["prev_close"], daily["prev_high"], daily["prev_low"] = prev_c, daily["high"].shift(), daily["low"].shift()
    r = np.log(rth["close"]).diff().where(rth["day"] == rth["day"].shift())
    r6 = np.log(rth["close"]).diff(6).where(rth["day"] == rth["day"].shift(6))
    v1 = r.groupby(rth["day"]).apply(lambda s: (s ** 2).sum())
    v6 = r6.groupby(rth["day"]).apply(lambda s: (s ** 2).sum() / 6)
    daily["vr"] = (v6.rolling(20).sum() / v1.rolling(20).sum()).shift()
    return rth, daily


def run(rth: pd.DataFrame, daily: pd.DataFrame, p: P, pv: float, tick: float) -> pd.DataFrame:
    cost_side = COMMISSION_SIDE + SLIP_TICKS * tick * pv
    cost_pts = 2 * cost_side / pv
    s0, s1 = (630, 870) if p.midday else tuple(int(x[:2]) * 60 + int(x[3:]) for x in (p.start, p.end))
    trades = []
    for day, d in rth.groupby("day"):
        if day not in daily.index or len(d) < 20:
            continue
        dd = daily.loc[day]
        if p.regime and not (dd["vr"] < 1):
            continue
        if p.vol_band and not (dd["atr_lo"] <= dd["atr"] <= dd["atr_hi"]):
            continue
        o, h, l, c = d["open"].to_numpy(), d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
        vw, sg, z, er = d["vwap"].to_numpy(), d["sigma"].to_numpy(), d["z"].to_numpy(), d["er"].to_numpy()
        mins = d.index.hour * 60 + d.index.minute
        n_side, losses, pos, i = {1: 0, -1: 0}, 0, None, 0
        while i < len(d) - 1:
            if pos is None:
                ok_time = s0 <= mins[i] < s1
                cand = 0
                if ok_time and losses < 2 and not np.isnan(z[i]):
                    zi = z[i - 1] if p.reversal_bar and i > 0 else z[i]
                    if zi <= -p.k:
                        cand = 1
                    elif zi >= p.k:
                        cand = -1
                    if cand and p.reversal_bar and not ((c[i] > o[i]) if cand > 0 else (c[i] < o[i])):
                        cand = 0
                    if cand and abs(c[i] - vw[i]) < p.edge_mult * cost_pts:
                        cand = 0
                    if cand and p.trend_veto and not (er[i] <= 0.5):
                        cand = 0
                    if cand and p.location:
                        reach = l[max(0, i - 3): i + 1].min() <= dd["prev_low"] if cand > 0 else h[max(0, i - 3): i + 1].max() >= dd["prev_high"]
                        cand = cand if reach else 0
                    if cand and p.htf_align and not ((dd["prev_close"] > dd["sma20"]) if cand > 0 else (dd["prev_close"] < dd["sma20"])):
                        cand = 0
                    if cand and n_side[cand] >= 2:
                        cand = 0
                if cand:
                    j = i + 1
                    entry = o[j]
                    stop = entry - cand * p.stop_sigma * sg[i]
                    pos = (cand, entry, stop, j, d.index[j])
                    n_side[cand] += 1
                    i = j
                    continue
                i += 1
                continue
            side, entry, stop, j0, t_in = pos
            tgt = vw[i - 1]
            exit_px, why = None, None
            if (l[i] <= stop) if side > 0 else (h[i] >= stop):
                exit_px, why = (min(o[i], stop) if side > 0 else max(o[i], stop)), "stop"
            elif (h[i] >= tgt) if side > 0 else (l[i] <= tgt):
                exit_px, why = (max(o[i], tgt) if side > 0 else min(o[i], tgt)), "vwap"
            elif i - j0 >= p.max_bars or mins[i] >= 950:
                exit_px, why = c[i], "time" if mins[i] < 950 else "eod"
            if exit_px is not None:
                pts = (exit_px - entry) * side
                pnl = pts * pv - 2 * cost_side
                trades.append({"day": day, "entry_time": t_in, "side": side, "pnl": pnl, "pts": pts, "why": why})
                losses += pnl < 0
                pos = None
            i += 1
        if pos is not None:
            side, entry, *_ , t_in = pos
            pnl = (c[-1] - entry) * side * pv - 2 * cost_side
            trades.append({"day": day, "entry_time": t_in, "side": side, "pnl": pnl, "pts": (c[-1] - entry) * side, "why": "eod"})
    return pd.DataFrame(trades)


def stats(t: pd.DataFrame) -> dict:
    if len(t) < 10:
        return {"trades": len(t)}
    p = t["pnl"]
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    day = p.groupby(t["day"]).sum()
    eq = day.cumsum()
    yr = p.groupby(pd.to_datetime(t["day"]).dt.year).sum()
    return {"trades": len(p), "net": round(float(p.sum()), 2), "pf": round(float(gw / gl), 3) if gl else None,
            "win": round(float((p > 0).mean()), 3), "avg": round(float(p.mean()), 2),
            "t": round(float(p.mean() / (p.std(ddof=1) / math.sqrt(len(p)))), 2),
            "worst_day": round(float(day.min()), 2), "max_dd": round(float((eq.cummax().clip(lower=0) - eq).max()), 2),
            "years_pos": f"{int((yr > 0).sum())}/{len(yr)}"}


def split(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if t.empty:
        return t, t
    d = pd.to_datetime(t["day"])
    return t[d < TRAIN_END], t[d >= TRAIN_END]


FILTERS = ["trend_veto", "regime", "reversal_bar", "location", "htf_align", "midday", "vol_band"]


def main() -> None:
    import sys
    if "--yahoo" in sys.argv:
        SOURCE["name"] = "yahoo"
    feats = {}
    for sym, (name, pv, tick) in MARKETS.items():
        if data_path(sym).exists():
            feats[sym] = session_features(load(sym))
    log: dict = {"plan": __doc__, "steps": []}

    def train_score(p: P) -> dict:
        """Pooled train stats over both markets (selection never looks at test data)."""
        ts = [split(run(*feats[s], p, MARKETS[s][1], MARKETS[s][2]))[0] for s in feats]
        return stats(pd.concat(ts)) if ts else {}

    # 1) choose k on train
    ks = {k: train_score(P(k=k)) for k in (2.0, 2.5, 3.0)}
    log["steps"].append({"step": "choose k", "train": ks})
    best_k = max(ks, key=lambda k: ks[k].get("t", -99))
    base = P(k=best_k)
    cur = ks[best_k]
    print("k:", {k: (v.get("pf"), v.get("t"), v.get("trades")) for k, v in ks.items()}, "->", best_k, flush=True)

    # 2) forward-add filters on train
    for f in FILTERS:
        cand = replace(base, **{f: True})
        sc = train_score(cand)
        keep = sc.get("pf") is not None and cur.get("pf") is not None and sc["pf"] > cur["pf"] and sc.get("t", -99) > cur.get("t", -99) and sc["trades"] >= 100
        log["steps"].append({"step": f"add {f}", "train": sc, "kept": keep})
        print(f"{f:13} train PF {sc.get('pf')} t {sc.get('t')} n {sc.get('trades')} -> {'KEEP' if keep else 'drop'}", flush=True)
        if keep:
            base, cur = cand, sc

    # 3) judge once on test, per market
    final = {}
    for sym in feats:
        tr, te = split(run(*feats[sym], base, MARKETS[sym][1], MARKETS[sym][2]))
        final[MARKETS[sym][0]] = {"train": stats(tr), "test": stats(te)}
        te.to_csv(ROOT / "trader" / f"vwap_revert_test_trades_{MARKETS[sym][0]}.csv", index=False)
    log["final_params"], log["final"] = asdict(base), final
    (ROOT / "trader" / "vwap_revert_results.json").write_text(json.dumps(log, indent=2, default=str))
    print(json.dumps({"params": asdict(base), "final": final}, indent=2, default=str))


if __name__ == "__main__":
    main()
