"""Pre-registered test of late-day intraday momentum on 2 years of OpenBB hourly bars.

Hypotheses (fixed before looking at results):
  H1  Gao, Han, Li & Zhou (2018): sign of the return from the prior 16:00 close to 10:00 today
      sets the direction for the last hour, 15:00 -> 16:00.
  H2  H1, only on days when |that return| is above its trailing 60-day median.
  H3  Baltussen, Da, Lammers & Martens (2021): sign of the return from the prior 16:00 close to
      15:00 today (the rest of the day) sets the direction for 15:00 -> 16:00.
Split: in-sample = first year, out-of-sample = second year, untouched until the variant is chosen.

    python truepath/bot/research.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "trader" / "data"
SPECS = {"MNQ": (2.0, 0.25), "MES": (5.0, 0.25)}
COMMISSION_RT, SLIP_TICKS_PER_SIDE = 3.10, 2
SPLIT = pd.Timestamp("2025-11-27", tz="America/New_York")


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{name}_1h.csv", index_col=0, parse_dates=True)
    df.index = df.index.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    return df[df.index.notna()].sort_index()


def at(df: pd.DataFrame, hhmm: str, col: str) -> pd.Series:
    x = df[df.index.strftime("%H:%M") == hhmm][col]
    x.index = x.index.normalize()
    return x[~x.index.duplicated()]


def futures_days(df: pd.DataFrame) -> pd.DataFrame:
    """One row per RTH day: prior 16:00 close, 10:00 close, 15:00 open, 16:00 close, last-hour high/low."""
    d = pd.DataFrame({
        "c10": at(df, "09:00", "close"),        # the 09:00-10:00 bar closes at 10:00
        "o15": at(df, "15:00", "open"),
        "c16": at(df, "15:00", "close"),        # the 15:00-16:00 bar closes at 16:00
        "h15": at(df, "15:00", "high"),
        "l15": at(df, "15:00", "low"),
    }).dropna()
    d["prev_c16"] = d["c16"].shift(1)
    return d.dropna()


def signals(d: pd.DataFrame) -> dict[str, pd.Series]:
    r_open = d["c10"] / d["prev_c16"] - 1
    r_rest = d["o15"] / d["prev_c16"] - 1
    big = r_open.abs() > r_open.abs().rolling(60, min_periods=20).median().shift(1)
    return {
        "H1": np.sign(r_open),
        "H2": np.sign(r_open).where(big, 0),
        "H3": np.sign(r_rest),
    }


def trade_pnl(d: pd.DataFrame, side: pd.Series, pv: float, tick: float) -> pd.DataFrame:
    slip = 2 * SLIP_TICKS_PER_SIDE * tick
    t = pd.DataFrame({"side": side})
    t = t[t["side"] != 0].join(d)
    t["points"] = (t["c16"] - t["o15"]) * t["side"] - slip
    t["pnl"] = t["points"] * pv - COMMISSION_RT
    t["worst"] = ((t["l15"] - t["o15"]).where(t["side"] > 0, t["o15"] - t["h15"]) - slip / 2) * pv - COMMISSION_RT / 2
    return t


def stats(t: pd.DataFrame) -> dict:
    if len(t) < 5:
        return {"trades": len(t)}
    p = t["pnl"]
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = p.cumsum()
    by_month = p.groupby(t.index.strftime("%Y-%m")).sum()
    return {"trades": len(p), "net": round(p.sum(), 2), "avg": round(p.mean(), 2),
            "t_stat": round(p.mean() / (p.std(ddof=1) / math.sqrt(len(p))), 2),
            "profit_factor": round(gw / gl, 2) if gl else None, "win_rate": round((p > 0).mean(), 3),
            "worst_trade": round(p.min(), 2), "worst_intrabar": round(t["worst"].min(), 2),
            "max_dd": round((eq.cummax().clip(lower=0) - eq).max(), 2),
            "profitable_months": f"{int((by_month > 0).sum())}/{len(by_month)}"}


def etf_check(name: str) -> dict:
    """Same idea on ETF bars, gross, in basis points: prior close -> 15:30 predicts 15:30 -> 16:00."""
    df = load(name)
    d = pd.DataFrame({"c1030": at(df, "09:30", "close"), "o1530": at(df, "15:30", "open"),
                      "c16": at(df, "15:30", "close")}).dropna()
    d["prev"] = d["c16"].shift(1)
    d = d.dropna()
    out = {}
    for h, r in {"H1": d["c1030"] / d["prev"] - 1, "H3": d["o1530"] / d["prev"] - 1}.items():
        bps = (d["c16"] / d["o1530"] - 1) * np.sign(r) * 1e4
        for label, m in (("in_sample", d.index < SPLIT), ("out_of_sample", d.index >= SPLIT)):
            x = bps[m]
            out[f"{h}_{label}"] = {"days": len(x), "avg_bps": round(x.mean(), 2),
                                   "t_stat": round(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))), 2)}
    return out


def main() -> None:
    report = {"split": str(SPLIT.date()), "costs": {"commission_rt": COMMISSION_RT, "slippage_ticks_per_side": SLIP_TICKS_PER_SIDE},
              "futures": {}, "etf_gross_check": {n: etf_check(n) for n in ("SPY", "QQQ")}}
    for sym, (pv, tick) in SPECS.items():
        d = futures_days(load(sym))
        for h, side in signals(d).items():
            t = trade_pnl(d, side, pv, tick)
            report["futures"][f"{sym}_{h}"] = {"in_sample": stats(t[t.index < SPLIT]),
                                               "out_of_sample": stats(t[t.index >= SPLIT])}
    out = ROOT / "trader" / "truepath_research_lastHour.json"
    out.write_text(json.dumps(report, indent=2, default=float))
    for k, v in report["futures"].items():
        i, o = v["in_sample"], v["out_of_sample"]
        print(f"{k:7} IS n={i['trades']} net={i.get('net')} PF={i.get('profit_factor')} t={i.get('t_stat')} | "
              f"OOS n={o['trades']} net={o.get('net')} PF={o.get('profit_factor')} t={o.get('t_stat')} months={o.get('profitable_months')}")
    for n, v in report["etf_gross_check"].items():
        print(n, {k: (x["avg_bps"], x["t_stat"]) for k, x in v.items()})
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
