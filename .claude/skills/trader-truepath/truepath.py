#!/usr/bin/env python3
"""TruePath Bot companion for trader-truepath. Standard library only.

    python3 truepath.py plan                         # today's MNQ order (after 10:00 ET)
    python3 truepath.py plan --symbols MNQ,MES --now "2026-11-25 10:05"
    python3 truepath.py account init --plan select50 --phase eval
    python3 truepath.py account log --pnl 230 [--date 2026-11-25]
    python3 truepath.py account show
    python3 truepath.py account payout --amount 900
    python3 truepath.py account funded               # passed: start the funded phase
    python3 truepath.py backtest [--symbols MNQ] [--split 2026-01-01] [--no-vix]

THE RULES (TruePath_Bot_v1.pine, the same on every surface)
  Range   high / low of the 09:00-10:00 ET bars.
  Side    VIX at 10:00 below yesterday's close -> long only; above -> short only.
  Entry   one stop order at the range high (long) or low (short), 10:00-15:00 ET.
  Stop    the other side of the range. Target 3R. Flat at 15:55 ET.
  Size    contracts = risk / (range x point value + round-trip costs), rounded down.

Data: Yahoo Finance chart API (free, delayed, unofficial): ES=F for MES, NQ=F for
MNQ, ^VIX. Never place an order from these numbers without checking your
platform's chart: Yahoo can lag and its continuous contract is not your contract.
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (compatible; day-trader-skill/2.0)"
HOSTS = ("https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com")
STATE_DIR = os.path.join("trader", "truepath")
ACCOUNT = os.path.join(STATE_DIR, "account.json")

# micro contract specs; Yahoo symbol of the full-size proxy
SPECS = {
    "MES": dict(yahoo="ES=F", pv=5.0, tick=0.25),
    "MNQ": dict(yahoo="NQ=F", pv=2.0, tick=0.25),
}
# Default risk per trade: the "safe" profile (one instrument) from the prop simulation.
DEFAULT_RISK = {"MES": 300.0, "MNQ": 500.0}
COMM_PER_SIDE = 1.55
SLIP_TICKS = 1
TARGET_R = 3.0
OR_START, OR_END, ENTRY_END, FLAT = 9 * 60, 10 * 60, 15 * 60, 15 * 60 + 55

# Tradeify plans as reported by third-party summaries in Nov 2026 - verify with Tradeify.
PLANS = {
    "select50": dict(name="Tradeify Select 50K", target=3000, dd=2000, dll=0, cons=0.40,
                     win_day=150, win_need=5, share=0.5, cap=2500, min_payout=250),
    "select100": dict(name="Tradeify Select 100K", target=6000, dd=3000, dll=0, cons=0.40,
                      win_day=250, win_need=5, share=0.5, cap=3000, min_payout=250),
    "growth50": dict(name="Tradeify Growth 50K", target=3000, dd=2000, dll=1250, cons=0.0,
                     win_day=150, win_need=5, share=0.5, cap=2500, min_payout=250),
    "growth100": dict(name="Tradeify Growth 100K", target=6000, dd=3500, dll=2500, cons=0.0,
                      win_day=250, win_need=5, share=0.5, cap=3000, min_payout=250),
}


# ── data ──────────────────────────────────────────────────────────────────────
def fetch_bars(sym, interval, rng):
    """[(datetime NY, o, h, l, c, v)] with the live, unfinished last bar dropped."""
    q = urllib.request.quote(sym)
    last = None
    for host in HOSTS:
        url = f"{host}/v8/finance/chart/{q}?interval={interval}&range={rng}&includePrePost=true"
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    res = json.load(r)["chart"]["result"][0]
                t = res.get("timestamp") or []
                qd = res["indicators"]["quote"][0]
                out = []
                for i, ts in enumerate(t):
                    o, h, l, c = qd["open"][i], qd["high"][i], qd["low"][i], qd["close"][i]
                    if None in (o, h, l, c):
                        continue
                    out.append((dt.datetime.fromtimestamp(ts, NY), o, h, l, c, qd["volume"][i] or 0))
                return out[:-1] if interval != "1d" else out
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
                break
            except (urllib.error.URLError, KeyError, IndexError, ValueError) as e:
                last = e
                break
    raise SystemExit(f"truepath.py: could not read {sym} from Yahoo ({last})")


def day_close(daily, day):
    """Last daily close strictly before `day`."""
    prev = [b for b in daily if b[0].date() < day]
    return prev[-1][4] if prev else None


def cost_per_ct(spec):
    return 2 * (COMM_PER_SIDE + SLIP_TICKS * spec["tick"] * spec["pv"])


# ── the rules ─────────────────────────────────────────────────────────────────
def mins(t):
    return t.hour * 60 + t.minute


def day_plan(bars, day, vix_at10, vix_prev, spec, risk, bar_minutes):
    """Range, side, order and (if the day has run) what happened. bars = that day's bars."""
    rng = [b for b in bars if OR_START <= mins(b[0]) and mins(b[0]) + bar_minutes <= OR_END]
    if not rng:
        return dict(status="no range bars")
    complete = any(mins(b[0]) + bar_minutes >= OR_END for b in rng)
    hi, lo = max(b[2] for b in rng), min(b[3] for b in rng)
    plan = dict(range_high=hi, range_low=lo, range_pts=round(hi - lo, 2))
    if not complete:
        plan["status"] = "range still forming (completes 10:00 ET)"
        return plan
    if vix_at10 is None or vix_prev is None:
        side = 0
    else:
        side = 1 if vix_at10 < vix_prev else -1 if vix_at10 > vix_prev else 0
    plan.update(vix_10=vix_at10, vix_prev_close=vix_prev, side={1: "long", -1: "short", 0: "none"}[side])
    if side == 0:
        plan["status"] = "no trade: VIX unchanged or no VIX data"
        return plan
    w = hi - lo
    per = w * spec["pv"] + cost_per_ct(spec)
    qty = int(math.floor(risk / per)) if w > 0 else 0
    entry, stop = (hi, lo) if side == 1 else (lo, hi)
    target = entry + side * TARGET_R * w
    plan.update(qty=qty, entry=entry, stop=stop, target=round(target, 2),
                risk_usd=round(qty * w * spec["pv"], 2), cost_usd=round(qty * cost_per_ct(spec), 2))
    if qty < 1:
        plan["status"] = f"no trade: one contract risks ${per:.0f}, more than ${risk:.0f}"
        return plan
    # replay the rest of the day
    after = [b for b in bars if mins(b[0]) >= OR_END]
    filled, result = None, None
    for b in after:
        m = mins(b[0])
        if filled is None:
            if m >= ENTRY_END:
                break
            if (side == 1 and b[2] >= entry) or (side == -1 and b[3] <= entry):
                filled = b[0]
                if (side == 1 and b[3] <= stop) or (side == -1 and b[2] >= stop):
                    result = ("stop", -w)          # same bar: assume the worst
                    break
            continue
        if m + bar_minutes > FLAT:
            result = ("flat 15:55", side * (b[4] - entry)); break
        if (side == 1 and b[3] <= stop) or (side == -1 and b[2] >= stop):
            result = ("stop", -w); break
        if (side == 1 and b[2] >= target) or (side == -1 and b[3] <= target):
            result = ("target 3R", TARGET_R * w); break
    if filled is None:
        plan["status"] = "waiting for the stop order to trigger" if (after and mins(after[-1][0]) < ENTRY_END) or not after else "not triggered (order cancelled at 15:00)"
        return plan
    plan["filled"] = filled.strftime("%H:%M")
    if result is None:
        last = after[-1][4]
        plan["status"] = "open"
        plan["open_pts"] = round(side * (last - entry), 2)
        plan["open_usd"] = round(plan["open_pts"] * spec["pv"] * qty, 2)
    else:
        plan["status"] = "closed: " + result[0]
        plan["result_pts"] = round(result[1], 2)
        plan["result_usd"] = round(result[1] * spec["pv"] * qty - qty * cost_per_ct(spec), 2)
    return plan


def webhook(sym, plan):
    """TradersPost-style JSON for the bracket stop order (check your bridge's docs)."""
    if plan.get("qty", 0) < 1:
        return None
    return {"ticker": sym, "action": "buy" if plan["side"] == "long" else "sell", "orderType": "stop",
            "stopPrice": plan["entry"], "quantity": plan["qty"],
            "stopLoss": {"type": "stop", "stopPrice": plan["stop"]},
            "takeProfit": {"limitPrice": plan["target"]}}


# ── commands ──────────────────────────────────────────────────────────────────
def cmd_plan(a):
    now = dt.datetime.strptime(a.now, "%Y-%m-%d %H:%M").replace(tzinfo=NY) if a.now else dt.datetime.now(NY)
    day = now.date()
    vix5 = fetch_bars("^VIX", "5m", "5d")
    vixd = fetch_bars("^VIX", "1d", "1mo")
    v10 = [b for b in vix5 if b[0].date() == day and mins(b[0]) + 5 <= OR_END and b[0] <= now]
    vix_at10 = v10[-1][4] if v10 and mins(v10[-1][0]) + 5 >= OR_END else None
    vix_prev = day_close(vixd, day)
    out = {"date": day.isoformat(), "as_of": now.strftime("%Y-%m-%d %H:%M"), "orders": {}}
    print(f"TruePath Bot plan · {day} · as of {now:%H:%M} ET (Yahoo, delayed)")
    for sym in a.symbols.split(","):
        spec = SPECS[sym]
        risk = a.risk if a.risk else DEFAULT_RISK[sym]
        bars = [b for b in fetch_bars(spec["yahoo"], "5m", "5d") if b[0].date() == day and b[0] + dt.timedelta(minutes=5) <= now]
        p = day_plan(bars, day, vix_at10, vix_prev, spec, risk, 5)
        out["orders"][sym] = p
        print(f"\n{sym}  ({spec['yahoo']} as proxy) · risk ${risk:.0f}")
        if "range_high" in p:
            print(f"  range 09:00-10:00  {p['range_low']:.2f} - {p['range_high']:.2f}  ({p['range_pts']} pts)")
        if "side" in p:
            print(f"  VIX at 10:00 {p['vix_10']:.2f} vs prior close {p['vix_prev_close']:.2f}  ->  {p['side'].upper()} side only")
        if p.get("qty", 0) >= 1:
            print(f"  order: {p['side']} {p['qty']} {sym} on a stop at {p['entry']:.2f} · stop {p['stop']:.2f} · target {p['target']:.2f} (3R)")
            print(f"         risk ${p['risk_usd']:.0f} + costs ${p['cost_usd']:.0f} · cancel at 15:00 if untriggered · flat 15:55")
            print("  webhook: " + json.dumps(webhook(sym, p)))
        print(f"  status: {p['status']}" + (f" · open {p['open_pts']:+.2f} pts (${p['open_usd']:+.0f})" if "open_pts" in p else "")
              + (f" · {p['result_pts']:+.2f} pts (${p['result_usd']:+.0f} after costs)" if "result_pts" in p else ""))
    os.makedirs(STATE_DIR, exist_ok=True)
    path = os.path.join(STATE_DIR, f"plan-{day.isoformat()}.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nWrote {path}. Nothing was placed: orders go through your TradingView alert and bridge, or by hand.")


def load_account():
    if not os.path.exists(ACCOUNT):
        raise SystemExit("No account yet: python3 truepath.py account init --plan select50 --phase eval")
    with open(ACCOUNT) as f:
        return json.load(f)


def save_account(acc):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(ACCOUNT, "w") as f:
        json.dump(acc, f, indent=2)


def account_state(acc):
    p = PLANS[acc["plan"]]
    bal = peak = 0.0
    best = 0.0
    wins = 0
    breached = False
    for d in acc["days"]:
        bal += d["pnl"]
        best = max(best, d["pnl"])
        if acc["phase"] == "funded" and d["pnl"] >= p["win_day"] and d["date"] > acc.get("last_payout", ""):
            wins += 1
        peak = max(peak, bal)
        if bal <= min(peak - p["dd"], 0.0):
            breached = True
    for po in acc.get("payouts", []):
        bal -= po["amount"]
    floor = min(peak - p["dd"], 0.0)
    return dict(p=p, bal=bal, peak=peak, floor=floor, room=bal - floor, best=best, wins=wins, breached=breached)


def cmd_account(a):
    if a.action == "init":
        if a.plan not in PLANS:
            raise SystemExit(f"plan must be one of {', '.join(PLANS)}")
        acc = {"plan": a.plan, "phase": "funded" if a.phase == "funded" else "eval", "days": [], "payouts": []}
        save_account(acc)
        print(f"Started {PLANS[a.plan]['name']} · {acc['phase']} · {ACCOUNT}")
        return
    acc = load_account()
    if a.action == "log":
        date = a.date or dt.datetime.now(NY).date().isoformat()
        acc["days"] = [d for d in acc["days"] if d["date"] != date] + [{"date": date, "pnl": a.pnl}]
        acc["days"].sort(key=lambda d: d["date"])
        save_account(acc)
    elif a.action == "payout":
        acc.setdefault("payouts", []).append({"date": dt.datetime.now(NY).date().isoformat(), "amount": a.amount})
        acc["last_payout"] = acc["payouts"][-1]["date"]
        save_account(acc)
    elif a.action == "funded":
        acc = {"plan": acc["plan"], "phase": "funded", "days": [], "payouts": [], "eval_history": acc["days"]}
        save_account(acc)
        print("Evaluation archived; funded phase started at $0.")
    s = account_state(acc)
    p = s["p"]
    print(f"{p['name']} · {acc['phase']} · {len(acc['days'])} days logged")
    print(f"  profit ${s['bal']:+,.0f} · peak ${s['peak']:,.0f} · drawdown floor ${s['floor']:+,.0f} · room ${s['room']:,.0f}")
    if s["breached"]:
        print("  FLOOR BREACHED on a logged day: the account has failed.")
    if acc["phase"] == "eval":
        share = s["best"] / s["bal"] if s["bal"] > 0 else None
        print(f"  target ${p['target']:,} · {100 * s['bal'] / p['target']:.0f}% done")
        if p["cons"]:
            print(f"  best day ${s['best']:,.0f}" + (f" = {100 * share:.0f}% of profit (must be <= {100 * p['cons']:.0f}% to pass)" if share else ""))
        ok = s["bal"] >= p["target"] and (not p["cons"] or (share is not None and share <= p["cons"]))
        print("  PASSED: stop trading and request the funded account." if ok else "  keep going.")
    else:
        elig = s["wins"] >= p["win_need"] and s["bal"] > 0
        amt = min(p["share"] * s["bal"], p["cap"])
        print(f"  winning days (>= ${p['win_day']}) since last payout: {s['wins']} / {p['win_need']}")
        if elig and amt >= p["min_payout"]:
            print(f"  PAYOUT READY: up to ${amt:,.0f} (50% of profit, cap ${p['cap']:,}). Then: account payout --amount N")
        else:
            print("  not eligible yet.")
    if s["room"] < 2 * DEFAULT_RISK["MNQ"]:
        print(f"  WARNING: room to the floor is ${s['room']:,.0f}; cut risk per trade or stop.")


def hourly_trades(sym_yahoo, vix_hourly, vix_daily, pv):
    bars = fetch_bars(sym_yahoo, "60m", "730d")
    by_day = {}
    for b in bars:
        if 9 <= b[0].hour <= 15:
            by_day.setdefault(b[0].date(), {})[b[0].hour] = b
    v9 = {b[0].date(): b[4] for b in vix_hourly if b[0].hour == 9}
    trades = []
    for day in sorted(by_day):
        g = by_day[day]
        if any(h not in g for h in range(9, 16)):
            continue
        hi, lo = g[9][2], g[9][3]
        w = hi - lo
        vp = day_close(vix_daily, day)
        v = v9.get(day)
        vside = 0 if (v is None or vp is None) else (1 if v < vp else -1 if v > vp else 0)
        res = None
        for hr in range(10, 15):
            b = g[hr]
            up, dn = b[2] >= hi, b[3] <= lo
            if up and dn:
                break
            if not (up or dn):
                continue
            d = 1 if up else -1
            e, s = (hi, lo) if d == 1 else (lo, hi)
            tgt = e + d * TARGET_R * w
            if (d == 1 and b[3] <= s) or (d == -1 and b[2] >= s):
                res = (d, -w); break
            for h2 in range(hr + 1, 16):
                c = g[h2]
                if (d == 1 and c[3] <= s) or (d == -1 and c[2] >= s):
                    res = (d, -w); break
                if (d == 1 and c[2] >= tgt) or (d == -1 and c[3] <= tgt):
                    res = (d, TARGET_R * w); break
            if res is None:
                res = (d, d * (g[15][4] - e))
            break
        if res and w > 0:
            cost_pts = cost_per_ct(dict(pv=pv, tick=0.25)) / pv
            trades.append(dict(date=day, d=res[0], pts=res[1] - cost_pts, R=(res[1] - cost_pts) / w, w=w, vix_ok=res[0] == vside))
    return trades


def stats(tr, label):
    n = len(tr)
    if n < 3:
        print(f"  {label}: {n} trades"); return
    x = [t["pts"] for t in tr]
    m = sum(x) / n
    sd = (sum((v - m) ** 2 for v in x) / (n - 1)) ** 0.5
    gw = sum(v for v in x if v > 0)
    gl = -sum(v for v in x if v < 0)
    print(f"  {label}: {n} trades · {m:+.2f} pts/trade · PF {gw / gl if gl else float('inf'):.2f} · t {m / (sd / n ** 0.5):.2f} · avg R {sum(t['R'] for t in tr) / n:+.3f}")


def payout_sim(daily, plan):
    p = PLANS[plan]
    n = len(daily)
    starts = max(0, n - 60)
    passed = paid_any = open_ = 0
    paid = 0.0
    done = 0
    for s in range(starts):
        bal = peak = best = 0.0; floor = -p["dd"]; i = s; ok = None
        while i < n:
            pnl, worst = daily[i]
            if bal + worst <= floor:
                ok = False; break
            bal += pnl; best = max(best, pnl)
            if bal > peak:
                peak = bal; floor = min(peak - p["dd"], 0.0)
            i += 1
            if bal >= p["target"] and (not p["cons"] or best <= p["cons"] * bal):
                ok = True; break
        if ok is None:
            open_ += 1
            continue
        done += 1
        if not ok:
            continue
        passed += 1
        bal = peak = 0.0; floor = -p["dd"]; wins = 0; got = 0.0
        while i < n:
            pnl, worst = daily[i]
            if bal + worst <= floor:
                break
            bal += pnl
            wins += pnl >= p["win_day"]
            if bal > peak:
                peak = bal; floor = min(peak - p["dd"], 0.0)
            if wins >= p["win_need"] and bal > 0 and min(p["share"] * bal, p["cap"]) >= p["min_payout"]:
                amt = min(p["share"] * bal, p["cap"]); got += amt; bal -= amt; wins = 0; peak = max(peak - amt, bal)
            i += 1
        paid += got
        paid_any += got > 0
    tot = done + open_
    if tot:
        print(f"  {p['name']}: {tot} evaluations · {100 * passed / tot:.0f}% passed · {100 * (done - passed) / tot:.0f}% failed · "
              f"{100 * open_ / tot:.0f}% unfinished at data end · {100 * paid_any / tot:.0f}% reached a payout · avg ${paid / tot:,.0f} withdrawn")


def cmd_backtest(a):
    split = dt.date.fromisoformat(a.split)
    print("Fetching ~2 years of hourly bars from Yahoo (ES=F, NQ=F, ^VIX)...")
    vh = fetch_bars("^VIX", "60m", "730d")
    vd = fetch_bars("^VIX", "1d", "5y")
    allt = {}
    syms = a.symbols.split(",")
    for sym in syms:
        spec = SPECS[sym]
        tr = hourly_trades(spec["yahoo"], vh, vd, spec["pv"])
        if not a.no_vix:
            tr = [t for t in tr if t["vix_ok"]]
        allt[sym] = (tr, spec)
        print(f"\n{sym} ({spec['yahoo']}, 09:00-10:00 range, 3R, costs in, VIX filter {'off' if a.no_vix else 'on'})")
        stats(tr, "all")
        stats([t for t in tr if t["date"] < split], f"before {split}")
        stats([t for t in tr if t["date"] >= split], f"from {split}")
        years = sorted({t["date"].year for t in tr})
        for y in years:
            stats([t for t in tr if t["date"].year == y], str(y))
    days = sorted({t["date"] for tr, _ in allt.values() for t in tr})
    daily = []
    for d in days:
        pnl = worst = 0.0
        for sym, (tr, spec) in allt.items():
            risk = a.risk if a.risk else DEFAULT_RISK[sym]
            for t in tr:
                if t["date"] == d:
                    qty = math.floor(risk / (t["w"] * spec["pv"] + cost_per_ct(spec)))
                    usd = qty * t["pts"] * spec["pv"]
                    pnl += usd
                    worst += min(usd, 0.0)
        daily.append((pnl, worst))
    risks = ", ".join(f"{s} ${a.risk if a.risk else DEFAULT_RISK[s]:.0f}" for s in syms)
    print(f"\nProp simulation · {risks} (whole contracts) · an evaluation started on every trade day")
    for plan in ("select50", "growth50"):
        payout_sim(daily, plan)
    print("\nHourly bars hide the order of events inside a bar; every ambiguity counts against the trade.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="truepath.py", description="TruePath Bot companion")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="today's MES / MNQ orders")
    p.add_argument("--risk", type=float, default=0, help="risk per trade per instrument ($); default MNQ $500, MES $300")
    p.add_argument("--symbols", default="MNQ")
    p.add_argument("--now", help='pin the clock, New York time, e.g. "2026-11-25 10:05"')
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("account", help="evaluation / funded tracker")
    p.add_argument("action", choices=["init", "log", "show", "payout", "funded"])
    p.add_argument("--plan", default="select50")
    p.add_argument("--phase", default="eval", choices=["eval", "funded"])
    p.add_argument("--pnl", type=float)
    p.add_argument("--date")
    p.add_argument("--amount", type=float)
    p.set_defaults(fn=cmd_account)
    p = sub.add_parser("backtest", help="re-test the rules on Yahoo hourly data + prop simulation")
    p.add_argument("--risk", type=float, default=0, help="default MNQ $500, MES $300")
    p.add_argument("--symbols", default="MNQ")
    p.add_argument("--split", default="2026-01-01")
    p.add_argument("--no-vix", action="store_true")
    p.set_defaults(fn=cmd_backtest)
    a = ap.parse_args(argv)
    if a.cmd == "account" and a.action == "log" and a.pnl is None:
        ap.error("account log needs --pnl")
    if a.cmd == "account" and a.action == "payout" and a.amount is None:
        ap.error("account payout needs --amount")
    a.fn(a)


if __name__ == "__main__":
    main()
