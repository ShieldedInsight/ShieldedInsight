"""Prop-account simulator: will this strategy reach a payout before it busts the account?

Replays daily P&L through an end-of-day trailing drawdown, then bootstraps 10,000 random orderings
of the days (in 5-day blocks) to estimate payout and bust odds.

    python truepath/bot/prop.py --tv-csv "List of trades.csv"       # TradingView Strategy Tester export
    python truepath/bot/prop.py --days days.csv                       # columns: date,pnl[,worst]

The rule defaults are an EOD-trailing 50K account with a $2,000 trail. Check them against your
firm's current rulebook (trail, where it locks, payout minimums) and pass the right values.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PropRules:
    start: float = 50_000.0
    trail: float = 2_000.0            # EOD trailing drawdown
    lock_at: float = 50_100.0         # the threshold stops rising here (Tradeify 50K: start + $100)
    daily_loss: float | None = None   # firm daily loss limit, if any (breach = day ends, not bust)
    win_day_min: float = 150.0        # a day counts toward payout only if it makes at least this
    win_days_needed: int = 5
    payout_buffer: float = 0.0        # balance must exceed start + this to request a payout
    horizon_days: int = 60            # trading days to reach the first payout


def run_account(pnl: np.ndarray, worst: np.ndarray, r: PropRules) -> dict:
    bal, hwm, thresh, wins = r.start, r.start, r.start - r.trail, 0
    for i, (p, w) in enumerate(zip(pnl, worst)):
        if r.daily_loss is not None:
            p, w = max(p, -r.daily_loss), max(w, -r.daily_loss)
        if bal + min(w, p) <= thresh:
            return {"outcome": "bust", "day": i + 1, "balance": thresh}
        bal += p
        wins += p >= r.win_day_min
        if wins >= r.win_days_needed and bal > r.start + r.payout_buffer:
            return {"outcome": "payout", "day": i + 1, "balance": bal, "withdrawable": bal - r.start}
        hwm = max(hwm, bal)
        thresh = min(max(thresh, hwm - r.trail), r.lock_at)
    return {"outcome": "neither", "day": len(pnl), "balance": bal}


def monte_carlo(days: pd.DataFrame, r: PropRules, runs: int = 10_000, block: int = 5, seed: int = 7) -> dict:
    pnl = days["pnl"].to_numpy(float)
    worst = days["worst"].to_numpy(float) if "worst" in days else np.minimum(pnl, 0)
    n, rng = len(pnl), np.random.default_rng(seed)
    out = {"payout": 0, "bust": 0, "neither": 0}
    payout_days, kept = [], []
    for _ in range(runs):
        starts = rng.integers(0, max(1, n - block + 1), size=r.horizon_days // block + 1)
        ix = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])[: r.horizon_days]
        res = run_account(pnl[ix], worst[ix], r)
        out[res["outcome"]] += 1
        if res["outcome"] == "payout":
            payout_days.append(res["day"])
            kept.append(res["withdrawable"])
    return {
        "runs": runs, "payout_pct": round(100 * out["payout"] / runs, 1), "bust_pct": round(100 * out["bust"] / runs, 1),
        "neither_pct": round(100 * out["neither"] / runs, 1),
        "median_days_to_payout": int(np.median(payout_days)) if payout_days else None,
        "median_profit_at_payout": round(float(np.median(kept)), 2) if kept else None,
    }


def evaluate(days: pd.DataFrame, r: PropRules = PropRules()) -> dict:
    d = days["pnl"]
    return {"rules": asdict(r), "days": len(d), "net": round(float(d.sum()), 2), "avg_day": round(float(d.mean()), 2),
            "worst_day": round(float(d.min()), 2), "worst_intraday": round(float(days.get("worst", d).min()), 2),
            "in_order": run_account(d.to_numpy(float), days.get("worst", d.clip(upper=0)).to_numpy(float), r),
            "monte_carlo": monte_carlo(days, r)}


def days_from_tradingview(path: str) -> pd.DataFrame:
    """TradingView 'List of trades' export: sums each trade's net P&L by its exit date; uses the
    worst run-up/drawdown column for the intraday low when it exists."""
    t = pd.read_csv(path)
    t.columns = [c.strip() for c in t.columns]
    exits = t[t["Type"].str.contains("Exit", case=False)].copy()
    pnl_col = next(c for c in exits.columns if c.lower().startswith(("net p&l", "profit")) and "%" not in c)
    dd_col = next((c for c in exits.columns if c.lower().startswith("drawdown") and "%" not in c), None)
    exits["date"] = pd.to_datetime(exits["Date/Time"]).dt.date
    g = exits.groupby("date")
    days = pd.DataFrame({"pnl": g[pnl_col].sum()})
    if dd_col:
        days["worst"] = np.minimum(days["pnl"], -g[dd_col].apply(lambda s: s.abs().max()))
    return days


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--tv-csv")
    src.add_argument("--days")
    for f, v in asdict(PropRules()).items():
        ap.add_argument("--" + f.replace("_", "-"), type=type(v) if v is not None else float, default=v)
    a = ap.parse_args()
    days = days_from_tradingview(a.tv_csv) if a.tv_csv else pd.read_csv(a.days, index_col=0)
    rules = PropRules(**{f: getattr(a, f) for f in asdict(PropRules())})
    print(json.dumps(evaluate(days, rules), indent=2, default=str))


if __name__ == "__main__":
    main()
