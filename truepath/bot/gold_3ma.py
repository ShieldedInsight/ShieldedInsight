"""TruePath Gold 3MA (book 3.13) on MGC 1h, Tradeify windows: backtest, prop check, live signal.

    python truepath/bot/gold_3ma.py backtest            # cached trader/data/GC_1h.csv, or --refresh to pull via OpenBB
    python truepath/bot/gold_3ma.py backtest --refresh
    python truepath/bot/gold_3ma.py signal --refresh    # what the rule wants on the next bar, as a governor alert

Rules (Kakushadze & Serur 3.13): long when MA3 > MA10 > MA21, out when MA3 <= MA10; short when
MA3 < MA10 < MA21, out when MA3 >= MA10. Flat over Tradeify's no-hold windows (16:59-17:59 ET
Mon-Thu, Friday 16:59 to the Sunday open), back in at the 18:00 open if the signal still holds.
1 MGC, $1.55/side + 2 ticks, fills at the next bar's open. Mirrors TruePath_Gold3MA_Tradeify_v1.pine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot import book151 as b          # noqa: E402  (data loader, 3.13 rule, Tradeify mask, P&L)
from bot.prop import PropRules, evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "trader" / "data" / "GC_1h.csv"


def refresh(start: str = "2024-11-27") -> None:
    from openbb import obb
    df = obb.equity.price.historical("GC=F", provider="yfinance", interval="1h", start_date=start).to_df()
    CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV)


def positions(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    raw = np.asarray(b.s_three_ma(df, "1h"), float)
    return raw, raw * b.tradeify_mask(df.index, "1h")


def session_days(pnl: pd.Series) -> pd.DataFrame:
    day = (pnl.index + pd.Timedelta(hours=6)).normalize()          # CME session starts 18:00 ET
    g = pnl.groupby(day)
    d = pd.DataFrame({"pnl": g.sum(), "worst": g.apply(lambda s: min(0.0, s.cumsum().min()))})
    return d[d["pnl"] != 0]


def backtest(rules: PropRules) -> dict:
    df = b.load("GC", "1h")
    _, pos = positions(df)
    pnl = b.pnl_series(df, pos, "GC")
    trades = b.count_trades(pos)
    days = session_days(pnl)
    mid = pnl.index[len(pnl) // 2]
    return {"bars": len(df), "from": str(df.index[0]), "to": str(df.index[-1]),
            "stats": b.stats(pnl, trades),
            "halves": {"first": round(float(pnl[pnl.index < mid].sum()), 2), "second": round(float(pnl[pnl.index >= mid].sum()), 2)},
            "prop": evaluate(days, rules)}


def signal(account: str) -> dict:
    df = b.load("GC", "1h")
    raw, _ = positions(df)
    last = df.index[-1]
    nxt = last + pd.Timedelta(hours=1)
    if nxt.hour == 17:                                   # no bars print 17:00-18:00 ET
        nxt += pd.Timedelta(hours=1)
    allowed = bool(b.tradeify_mask(pd.DatetimeIndex([last, nxt]), "1h")[0])
    target = int(raw[-1]) if allowed else 0
    return {"bar": str(last), "next_bar": str(nxt), "close": float(df["close"].iloc[-1]), "rule_wants": int(raw[-1]),
            "allowed_next_bar": allowed,
            "alert": {"acct": account, "sym": "MGC", "action": "buy" if target > 0 else "sell" if target < 0 else "flat",
                      "target": target, "price": float(df["close"].iloc[-1])},
            "note": "No stop is attached (the tested rule has none); the governor blocks entries without a stop."}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["backtest", "signal"])
    ap.add_argument("--refresh", action="store_true", help="pull fresh GC=F 1h bars through OpenBB first")
    ap.add_argument("--account", default="TP-01")
    a = ap.parse_args()
    if a.refresh:
        refresh()
    out = backtest(PropRules()) if a.cmd == "backtest" else signal(a.account)
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
