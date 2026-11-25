"""Bar-by-bar engine for TruePath_MACross_RTH_v1, matching TradingView's broker emulator.

Mirrors the Notion script's settings: process_orders_on_close = false (an order placed at a bar's
close fills at the NEXT bar's open), slippage in ticks against you on every market and stop fill,
commission per contract per fill, strategy.close_all(immediately = true) fills at the bar's close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pandas as pd

SPECS = {"MNQ": (2.0, 0.25), "NQ": (20.0, 0.25), "MES": (5.0, 0.25), "ES": (50.0, 0.25)}


@dataclass(frozen=True)
class MACrossParams:
    sma_len: int = 7
    confirm: int = 1
    entry_start: time = time(9, 30)   # bar START time inside [entry_start, entry_end)
    entry_end: time = time(15, 55)
    flat_at: time = time(15, 55)      # flatten on the bar whose close reaches this time
    qty: int = 2
    cat_pts: float | None = 100.0     # catastrophe stop, points from the fill
    daily_loss: float | None = None   # closed + open P&L; flatten and stop for the day
    daily_target: float | None = None
    commission_side: float = 1.55
    slippage_ticks: int = 2


@dataclass
class Result:
    trades: list[dict] = field(default_factory=list)
    days: pd.DataFrame | None = None   # per trading day: pnl, worst intraday equity vs day start, trades


def trading_day(ts: pd.Timestamp) -> pd.Timestamp:
    """CME day starts at 18:00 ET, as TradingView's timeframe.change("D") does on futures."""
    return (ts + pd.Timedelta(hours=6)).normalize()


def run_ma_cross(df: pd.DataFrame, p: MACrossParams, point_value: float, tick: float) -> Result:
    close = df["close"]
    sma = close.rolling(p.sma_len).mean()
    above, below = (close > sma).to_numpy(), (close < sma).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    idx = df.index
    bar_min = pd.Series(idx).diff().dt.total_seconds().div(60).mode().iloc[0]
    starts = idx.time
    closes = (idx + pd.Timedelta(minutes=bar_min)).time
    tdays = [trading_day(t) for t in idx]
    slip = p.slippage_ticks * tick

    res = Result()
    pos, avg, entry_ts = 0, 0.0, None
    pending = None
    b_cnt = s_cnt = 0
    cur_day, day_start_real, realized = None, 0.0, 0.0
    day_rows: dict = {}
    locked = False
    trades_today = 0

    def fill(target: int, px: float, ts, why: str) -> None:
        nonlocal pos, avg, entry_ts, realized, trades_today
        delta = target - pos
        if delta == 0:
            return
        realized -= abs(delta) * p.commission_side
        if pos != 0 and (target == 0 or (target > 0) != (pos > 0)):
            gross = (px - avg) * pos * point_value
            realized += gross
            res.trades.append({"entry_time": str(entry_ts), "exit_time": str(ts), "side": "long" if pos > 0 else "short",
                               "qty": abs(pos), "entry": avg, "exit": px, "reason": why,
                               "pnl": round(gross - 2 * abs(pos) * p.commission_side, 2)})
            pos = 0
        if target != 0:
            avg, pos, entry_ts = px, target, ts
            trades_today += 1

    for i in range(len(df)):
        ts, td = idx[i], tdays[i]
        if td != cur_day:
            if cur_day is not None:
                day_rows[cur_day]["pnl"] = round(realized - day_start_real + (pos and (c[i - 1] - avg) * pos * point_value), 2)
            cur_day, day_start_real, locked, trades_today = td, realized, False, 0
            day_rows[td] = {"pnl": 0.0, "worst": 0.0, "trades": 0}

        # 1) orders from the previous close fill at this open
        if pending is not None:
            side = 1 if pending > pos else -1
            fill(pending, o[i] + side * slip, ts, "reverse" if pending != 0 else "flat")
            pending = None

        # 2) catastrophe stop inside the bar
        if pos and p.cat_pts:
            stop = avg - p.cat_pts if pos > 0 else avg + p.cat_pts
            if pos > 0 and l[i] <= stop:
                fill(0, min(o[i], stop) - slip, ts, "cat_stop")
            elif pos < 0 and h[i] >= stop:
                fill(0, max(o[i], stop) + slip, ts, "cat_stop")

        # worst equity in the bar, against the day's start (for intraday trailing-drawdown checks)
        adverse = (l[i] if pos > 0 else h[i]) if pos else c[i]
        worst = realized - day_start_real + (pos and (adverse - avg) * pos * point_value)
        day_rows[td]["worst"] = min(day_rows[td]["worst"], round(worst, 2))

        # 3) script runs at the close
        b_cnt = b_cnt + 1 if above[i] else 0
        s_cnt = s_cnt + 1 if below[i] else 0
        long_sig, short_sig = b_cnt == p.confirm, s_cnt == p.confirm
        day_pnl = realized - day_start_real + (pos and (c[i] - avg) * pos * point_value)
        if (p.daily_loss and day_pnl <= -p.daily_loss) or (p.daily_target and day_pnl >= p.daily_target):
            locked = True
        # same test as the Pine script: closeMin < 18:00 and closeMin + tfMin > flatMin
        close_min = closes[i].hour * 60 + closes[i].minute
        flat_bar = close_min < 18 * 60 and close_min + bar_min > p.flat_at.hour * 60 + p.flat_at.minute
        in_sess = p.entry_start <= starts[i] < p.entry_end

        if pos and (flat_bar or locked):
            fill(0, c[i] - (slip if pos > 0 else -slip), ts, "eod" if flat_bar else "day_lock")
        elif in_sess and not flat_bar and not locked:
            if long_sig and pos <= 0:
                pending = p.qty
            elif short_sig and pos >= 0:
                pending = -p.qty
        day_rows[td]["trades"] = trades_today

    if cur_day is not None:
        day_rows[cur_day]["pnl"] = round(realized - day_start_real + (pos and (c[-1] - avg) * pos * point_value), 2)
    days = pd.DataFrame.from_dict(day_rows, orient="index")
    res.days = days[days["trades"] > 0]
    return res


def summarize(res: Result) -> dict:
    if not res.trades:
        return {"trades": 0}
    pnl = pd.Series([t["pnl"] for t in res.trades])
    d = res.days["pnl"]
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = d.cumsum()
    top = pnl.sort_values(ascending=False)
    n_top = max(1, int(len(pnl) * 0.02))
    t_stat = pnl.mean() / (pnl.std(ddof=1) / len(pnl) ** 0.5) if len(pnl) > 2 and pnl.std() > 0 else None
    return {
        "trades": len(pnl), "days": int(d.size), "net": round(float(pnl.sum()), 2),
        "profit_factor": round(float(gw / gl), 2) if gl else None, "win_rate": round(float((pnl > 0).mean()), 3),
        "avg_trade": round(float(pnl.mean()), 2), "t_stat": round(float(t_stat), 2) if t_stat is not None else None,
        "winning_days": int((d > 0).sum()), "avg_day": round(float(d.mean()), 2),
        "best_day": round(float(d.max()), 2), "worst_day": round(float(d.min()), 2),
        "worst_intraday": round(float(res.days["worst"].min()), 2),
        "max_dd_eod": round(float((eq.cummax().clip(lower=0) - eq).max()), 2),
        "top2pct_share_of_net": round(float(top.iloc[:n_top].sum() / pnl.sum()), 2) if pnl.sum() > 0 else None,
    }
