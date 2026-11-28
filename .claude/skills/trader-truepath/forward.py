#!/usr/bin/env python3
"""TruePath forward test: two weeks of paper trading on a simulated Tradeify Select 50K account.

The rules below were frozen BEFORE the first forward session (2026-11-30). Research of 2026-11-28 on
hourly NQ / ES futures, Jul 2024 - Nov 25 2026 (all data, 2026 included): four candidates, the
opening-range rule kept; one refinement adopted for MES only because it beat the plain rule in each of
H2 2024, 2025 and 2026 (skip days whose range is wider than 1.5x its 20-session median); MES $300
chosen for the account, then raised to $400 risk (~3 contracts) on request (Select 50K simulation:
$400 84% passed / 12% failed, median 57 sessions; $300 91% / 0%, 116; $500 80% / 20%).
Each run settles every finished session of the window that is not in the ledger yet, from Yahoo
5-minute bars, so a missed run is caught up later. Nothing here places an order.

  python3 forward.py settle        # settle finished sessions, update the account and the report
  python3 forward.py status        # print the account and the trades so far

Rules (MES in the account, MNQ logged alongside as a shadow, not in the account):
  range   high / low of 09:00-10:00 ET (5-minute bars 09:00..09:55)
  side    the 09:00-10:00 candle: close above its open -> long only, below -> short only
  entry   the FIRST touch of a range edge between 10:00 and 15:00 must be on that side, else no
          trade; stop order at the edge (a gap past it fills at the bar's open)
  stop    the other edge;  target 3R;  flat at 15:55 ET
  ties    a bar that touches both edges before entry -> no trade; a bar touching stop and target ->
          stop; the entry bar can only stop out
  filter  MES only: skip the day if the range is wider than 1.5x the median range of the prior 20 sessions
  size    contracts = floor(risk / (range x point value + costs)); MES $400, MNQ $500; 0 -> skip
  costs   $1.55 commission + 1 tick slippage per side
"""
import csv
import datetime as dt
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from truepath import fetch_bars, PLANS, NY  # noqa: E402

RULES_VERSION = "TP-ORB-forward-3 (frozen 2026-11-28)"
START, END = dt.date(2026, 11, 30), dt.date(2026, 12, 11)
PLAN = "select50"
MARKETS = {  # role: account = counts toward the prop account; shadow = logged only
    "MES": dict(yahoo="ES=F", pv=5.0, tick=0.25, risk=400.0, role="account", max_width=1.5),
    "MNQ": dict(yahoo="NQ=F", pv=2.0, tick=0.25, risk=500.0, role="shadow", max_width=None),
}
COMM, SLIP, TARGET_R = 1.55, 1, 3.0
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "trader", "truepath", "forward")
LEDGER = os.path.join(OUT, "ledger.csv")
FIELDS = ["date", "sym", "role", "or_high", "or_low", "width", "side", "result", "entry_time", "entry",
          "stop", "target", "exit_time", "exit", "qty", "pts", "pnl", "R", "note", "rules", "code", "settled_at"]


def hm(t):
    return t.hour * 60 + t.minute


def or_width(bars, day):
    orb = [x for x in bars if x[0].date() == day and 9 * 60 <= hm(x[0]) < 10 * 60]
    return max(x[2] for x in orb) - min(x[3] for x in orb) if len(orb) >= 12 else None


def prior_median_width(bars, day, n=20):
    days = sorted({x[0].date() for x in bars if x[0].date() < day and x[0].weekday() < 5})
    w = [v for v in (or_width(bars, d) for d in days) if v is not None][-n:]
    if len(w) < n:
        return None
    w.sort()
    return (w[n // 2 - 1] + w[n // 2]) / 2


def settle_day(bars, day, m):
    """One session from 5-minute bars -> ledger row (dict), or None if the data is incomplete."""
    b = [x for x in bars if x[0].date() == day and 9 * 60 <= hm(x[0]) < 15 * 60 + 55]
    orb = [x for x in b if hm(x[0]) < 10 * 60]
    after = [x for x in b if hm(x[0]) >= 10 * 60]
    if len(orb) < 12 or not after or hm(after[-1][0]) < 15 * 60 + 50:
        return None
    hi, lo = max(x[2] for x in orb), min(x[3] for x in orb)
    w = hi - lo
    side = 1 if orb[-1][4] > orb[0][1] else -1 if orb[-1][4] < orb[0][1] else 0
    cost = 2 * (COMM + SLIP * m["tick"] * m["pv"])
    per_ct = w * m["pv"] + cost
    qty = int(m["risk"] // per_ct) if w > 0 else 0
    row = dict(date=day.isoformat(), or_high=hi, or_low=lo, width=round(w, 2),
               side={1: "long", -1: "short", 0: "none"}[side], qty=qty, pts=0, pnl=0.0, R=0.0, note="")
    if side == 0 or w <= 0:
        return {**row, "result": "no trade", "note": "flat opening candle"}
    if m.get("max_width"):
        med = prior_median_width(bars, day)
        if med is None:
            return None
        if w > m["max_width"] * med:
            return {**row, "result": "no trade", "note": f"range {w:.2f} > {m['max_width']}x 20-day median {med:.2f}"}
    entry = stop = tgt = None
    i_fill = None
    for i, x in enumerate(after):
        if hm(x[0]) >= 15 * 60:
            break
        up, dn = x[2] >= hi, x[3] <= lo
        if up and dn:
            return {**row, "result": "no trade", "note": f"both edges in the {x[0]:%H:%M} bar"}
        if not (up or dn):
            continue
        d = 1 if up else -1
        if d != side:
            return {**row, "result": "no trade", "note": f"first break {'up' if d == 1 else 'down'} at {x[0]:%H:%M}, against the side"}
        edge = hi if d == 1 else lo
        entry = max(edge, x[1]) if d == 1 else min(edge, x[1])
        stop, tgt = (lo, entry + TARGET_R * w) if d == 1 else (hi, entry - TARGET_R * w)
        i_fill = i
        break
    if entry is None:
        return {**row, "result": "no trade", "note": "no break before 15:00"}
    if qty == 0:
        return {**row, "result": "skipped", "note": f"range {w:.2f} pts: 1 contract would risk ${per_ct:.0f} > ${m['risk']:.0f}",
                "entry_time": f"{after[i_fill][0]:%H:%M}", "entry": entry, "stop": stop, "target": tgt}
    x_px = x_t = outcome = None
    for j in range(i_fill, len(after)):
        x = after[j]
        hit_s = x[3] <= stop if side == 1 else x[2] >= stop
        hit_t = (x[2] >= tgt if side == 1 else x[3] <= tgt) and j > i_fill
        if hit_s:
            x_px = min(stop, x[1]) if side == 1 and j > i_fill else max(stop, x[1]) if j > i_fill else stop
            x_t, outcome = x[0], "stop"
            break
        if hit_t:
            x_px, x_t, outcome = tgt, x[0], "target"
            break
    if outcome is None:
        x_px, x_t, outcome = after[-1][4], after[-1][0], "end of day"
    pts = side * (x_px - entry)
    pnl = qty * (pts * m["pv"] - cost)
    return {**row, "result": outcome, "entry_time": f"{after[i_fill][0]:%H:%M}", "entry": round(entry, 2), "stop": round(stop, 2),
            "target": round(tgt, 2), "exit_time": f"{x_t:%H:%M}", "exit": round(x_px, 2), "pts": round(pts, 2),
            "pnl": round(pnl, 2), "R": round(pnl / (qty * per_ct), 2)}


def read_ledger():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, newline="") as f:
        return list(csv.DictReader(f))


def account(rows):
    p = PLANS[PLAN]
    days = {}
    for r in rows:
        if r["role"] == "account":
            days[r["date"]] = days.get(r["date"], 0.0) + float(r["pnl"] or 0)
    bal = peak = best = 0.0
    status, hist = "in evaluation", []
    for d in sorted(days):
        bal += days[d]
        best = max(best, days[d])
        peak = max(peak, bal)
        floor = min(peak - p["dd"], 0.0)
        if status == "in evaluation":
            if bal <= floor:
                status = f"FAILED on {d}"
            elif bal >= p["target"] and best <= p["cons"] * bal:
                status = f"PASSED on {d}"
        hist.append(dict(date=d, pnl=round(days[d], 2), balance=round(50000 + bal, 2), floor=round(50000 + floor, 2)))
    floor = min(peak - p["dd"], 0.0)
    need_cons = best / p["cons"] if best > 0 else 0
    return dict(plan=p["name"], start=50000.0, balance=round(50000 + bal, 2), profit=round(bal, 2), target=p["target"],
                floor=round(50000 + floor, 2), room=round(bal - floor, 2), best_day=round(best, 2),
                consistency_needs_profit_of=round(need_cons, 2), status=status, days=hist)


def git_head():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def write_report(rows, acc):
    trades = [r for r in rows if r["result"] in ("target", "stop", "end of day")]
    lines = [f"# TruePath forward test · {START:%b %-d} – {END:%b %-d, %Y}", "",
             f"Rules: {RULES_VERSION} · account: {acc['plan']} · MES $400 risk (1.5x range filter) in the account, MNQ $500 logged as a shadow.", "",
             f"**Account:** ${acc['balance']:,.2f} ({acc['profit']:+,.2f}) · floor ${acc['floor']:,.2f} · room ${acc['room']:,.2f} · "
             f"target +${acc['target']:,} · best day ${acc['best_day']:,.2f} · **{acc['status']}**", ""]
    for sym in MARKETS:
        t = [r for r in trades if r["sym"] == sym]
        if t:
            pn = sum(float(r["pnl"]) for r in t)
            w = sum(float(r["pnl"]) > 0 for r in t)
            lines.append(f"- {sym} ({MARKETS[sym]['role']}): {len(t)} trades, {w} winners, P&L ${pn:,.2f}, avg R {sum(float(r['R']) for r in t) / len(t):+.2f}")
    lines += ["", "| Date | Mkt | Side | Result | Entry | Stop | Target | Exit | Qty | P&L | R | Note |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['date']} | {r['sym']} | {r['side']} | {r['result']} | {r.get('entry_time','')} {r.get('entry','')} | {r.get('stop','')} | "
                     f"{r.get('target','')} | {r.get('exit_time','')} {r.get('exit','')} | {r.get('qty','')} | {r.get('pnl','')} | {r.get('R','')} | {r.get('note','')} |")
    lines += ["", "Backtest expectation per trade (hourly, Jul 2024 – Nov 2026): MES with the filter win ≈ 55%, avg ≈ +0.24 R; MNQ win ≈ 56%, avg ≈ +0.18 R. Ten sessions is far too few to confirm or reject the edge;",
              "this log checks that the rules run as designed on unseen data. Yahoo 5-minute futures data; history, not advice."]
    with open(os.path.join(OUT, "README.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def cmd_settle():
    os.makedirs(OUT, exist_ok=True)
    rows = read_ledger()
    done = {(r["date"], r["sym"]) for r in rows}
    now = dt.datetime.now(NY)
    last = min(END, now.date() if hm(now) >= 16 * 60 + 5 else now.date() - dt.timedelta(days=1))
    days = [START + dt.timedelta(days=i) for i in range((last - START).days + 1)] if last >= START else []
    days = [d for d in days if d.weekday() < 5]
    added, waiting = [], []
    code = git_head()
    for sym, m in MARKETS.items():
        todo = [d for d in days if (d.isoformat(), sym) not in done]
        if not todo:
            continue
        bars = fetch_bars(m["yahoo"], "5m", "60d")
        for d in todo:
            r = settle_day(bars, d, m)
            if r is None:
                have = any(x[0].date() == d for x in bars)
                if not have and (now.date() - d).days >= 3:
                    r = dict(date=d.isoformat(), result="no session", note="no bars (holiday or data gap)")
                else:
                    waiting.append(f"{sym} {d}")
                    continue
            r.update(sym=sym, role=m["role"], rules=RULES_VERSION, code=code, settled_at=now.isoformat(timespec="minutes"))
            rows.append(r)
            added.append(r)
    rows.sort(key=lambda r: (r["date"], r["sym"]))
    with open(LEDGER, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    acc = account(rows)
    with open(os.path.join(OUT, "account.json"), "w") as f:
        json.dump(acc, f, indent=2)
    write_report(rows, acc)
    for r in added:
        print(f"{r['date']} {r['sym']:3} {r['result']:10} {r.get('side', ''):5} qty {r.get('qty', '')} P&L {r.get('pnl', '')} {r.get('note', '')}")
    if waiting:
        print("waiting for data:", ", ".join(waiting))
    if not added and not waiting:
        print("nothing new to settle" + (" (window not started)" if not days else ""))
    print(f"account: {acc['status']} · balance ${acc['balance']:,.2f} · floor ${acc['floor']:,.2f} · room ${acc['room']:,.2f}")
    print("window complete" if last >= END and not waiting else f"window {START} – {END}")


def cmd_status():
    rows = read_ledger()
    print(json.dumps(account(rows), indent=2))
    for r in rows:
        print(r["date"], r["sym"], r["result"], r.get("pnl", ""), r.get("note", ""))


if __name__ == "__main__":
    {"settle": cmd_settle, "status": cmd_status}.get((sys.argv[1:] or ["settle"])[0], cmd_status)()
