"""TruePath prop governor: TradingView alert -> prop-rule check -> TradersPost.

KeyLevel Builder (or any TruePath strategy) keeps its signals in TradingView. Each alert it sends
comes here first. Entries must pass every prop rule below or they are blocked; exits always pass.
At the flat-by time the governor closes anything still open on its own.

    python truepath/bot/governor.py --config trader/governor.json              # dry run (default)
    python truepath/bot/governor.py --config trader/governor.json --live       # forwards to TradersPost
    python truepath/bot/governor.py --config trader/governor.json --check '{"acct":"TP-01","sym":"MNQ","action":"buy","target":1,"stop":21000,"price":21050}'

Environment:
    GOVERNOR_TOKEN          secret path segment; TradingView posts to https://<host>/tv/<GOVERNOR_TOKEN>
    TRADERSPOST_WEBHOOK_URL your TradersPost strategy webhook URL (only read with --live)

Alert body: KeyLevel Builder's alert_message JSON, i.e. {"acct","sym","action":"buy|sell|flat",
"target":signed contracts,"stop":price}, plus "price" (bar close) and "tp" (first target) from
truepath/bot/KL_BUILDER_PATCH.md. Without "price" the governor cannot estimate intraday P&L and the
headroom check uses only the last balance you posted to /balance.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time as _time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
POINT_VALUE = {"MNQ": 2.0, "NQ": 20.0, "MES": 5.0, "ES": 50.0, "MGC": 10.0, "GC": 100.0}


@dataclass
class Config:
    account: str = "TP-01"
    start_balance: float = 50_000.0
    trail: float = 2_000.0                 # EOD trailing drawdown
    lock_at: float = 50_000.0              # threshold stops trailing at this balance
    cushion: float = 250.0                 # never let a stop-out land closer than this to the threshold
    daily_loss_lock: float = 600.0         # estimated day P&L at or below -this blocks new entries
    daily_profit_lock: float | None = None # optional: stop for the day after this much profit
    max_contracts: int = 2
    max_trades_per_day: int = 4
    entry_start: str = "09:30"
    entry_end: str = "15:30"
    flat_by: str = "15:55"
    blackout: list[str] = field(default_factory=list)   # "HH:MM-HH:MM" windows (e.g. CPI, FOMC) with no entries
    commission_side: float = 1.55
    symbols: dict[str, str] = field(default_factory=lambda: {"MNQ": "MNQ1!"})  # alert root -> TradersPost ticker
    state_file: str = "trader/state/governor.json"
    log_file: str = "trader/state/governor_log.jsonl"


def hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


class Governor:
    def __init__(self, cfg: Config, live: bool = False, now=None):
        self.cfg, self.live = cfg, live
        self.now = now or (lambda: datetime.now(NY))
        self.lock = threading.Lock()
        self.state_path, self.log_path = ROOT / cfg.state_file, ROOT / cfg.log_file
        self.state = self._load()

    # ── state ──────────────────────────────────────────────────────────────
    def _fresh_day(self, day: str) -> dict:
        s = self.state if hasattr(self, "state") else {}
        return {"day": day, "eod_balance": s.get("eod_balance", self.cfg.start_balance),
                "hwm": s.get("hwm", self.cfg.start_balance), "threshold": s.get("threshold", self.cfg.start_balance - self.cfg.trail),
                "realized": 0.0, "trades": 0, "locked": None, "pos": {}}

    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"day": None, "eod_balance": self.cfg.start_balance, "hwm": self.cfg.start_balance,
                "threshold": self.cfg.start_balance - self.cfg.trail, "realized": 0.0, "trades": 0, "locked": None, "pos": {}}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def _roll_day(self) -> None:
        today = self.now().strftime("%Y-%m-%d")
        if self.state.get("day") != today:
            if self.state.get("day") is not None and not self.state.get("balance_posted"):
                # No broker balance posted: carry the estimate forward and trail from it.
                self.end_of_day(self.state["eod_balance"] + self.state["realized"])
            self.state = self._fresh_day(today)

    def end_of_day(self, balance: float) -> dict:
        """Post the broker's end-of-day balance (source of truth for the trailing threshold)."""
        s = self.state
        s["eod_balance"] = balance
        s["hwm"] = max(s["hwm"], balance)
        s["threshold"] = min(max(s["threshold"], s["hwm"] - self.cfg.trail), self.cfg.lock_at)
        s["balance_posted"] = True
        self._save()
        return {"eod_balance": balance, "threshold": s["threshold"], "room": round(balance - s["threshold"], 2)}

    # ── P&L estimate from alert prices ────────────────────────────────────
    def _mark(self, root: str, price: float | None) -> float:
        p = self.state["pos"].get(root)
        if not p or price is None:
            return 0.0
        return (price - p["avg"]) * p["qty"] * POINT_VALUE.get(root, 0)

    def _apply_fill(self, root: str, target: int, price: float | None) -> None:
        pos = self.state["pos"].get(root, {"qty": 0, "avg": 0.0})
        delta = target - pos["qty"]
        self.state["realized"] -= abs(delta) * self.cfg.commission_side
        if pos["qty"] and price is not None and (target == 0 or (target > 0) != (pos["qty"] > 0)):
            self.state["realized"] += (price - pos["avg"]) * pos["qty"] * POINT_VALUE.get(root, 0)
            pos = {"qty": 0, "avg": 0.0}
        if target == 0:
            self.state["pos"].pop(root, None)
        else:
            if (target > 0) != (pos["qty"] > 0) or pos["qty"] == 0:
                self.state["pos"][root] = {"qty": target, "avg": price}
                self.state["trades"] += 1
            else:
                self.state["pos"][root] = {"qty": target, "avg": pos["avg"]}

    # ── the check ──────────────────────────────────────────────────────────
    def check(self, a: dict) -> tuple[bool, list[str], str]:
        """Returns (allowed, reasons, kind). kind is 'entry' or 'exit'."""
        c, s, now = self.cfg, self.state, self.now()
        root, action = str(a.get("sym", "")).upper(), str(a.get("action", "")).lower()
        target = int(a.get("target", 0)) if action != "flat" else 0
        price, stop = a.get("price"), a.get("stop")
        cur = s["pos"].get(root, {"qty": 0})["qty"]
        is_exit = target == 0 or (cur != 0 and (target > 0) == (cur > 0) and abs(target) < abs(cur))
        kind = "exit" if is_exit else "entry"
        why: list[str] = []
        if a.get("acct") not in (None, c.account):
            why.append(f"alert is for account {a.get('acct')}, this governor runs {c.account}")
        if root not in c.symbols:
            why.append(f"{root or '(none)'} is not an allowed symbol")
        if action not in ("buy", "sell", "flat"):
            why.append(f"unknown action {action!r}")
        if kind == "exit":
            return (not why, why, kind)

        t = now.time()
        if not (hm(c.entry_start) <= t < hm(c.entry_end)):
            why.append(f"{t:%H:%M} ET is outside the entry window {c.entry_start}-{c.entry_end}")
        for w in c.blackout:
            a0, a1 = w.split("-")
            if hm(a0) <= t < hm(a1):
                why.append(f"news blackout {w}")
        if abs(target) > c.max_contracts:
            why.append(f"{abs(target)} contracts is over the {c.max_contracts}-contract limit")
        if s["trades"] >= c.max_trades_per_day:
            why.append(f"already {s['trades']} trades today (limit {c.max_trades_per_day})")
        if s.get("locked"):
            why.append(f"day is locked: {s['locked']}")
        if stop is None:
            why.append("entry has no stop")

        day_pnl = s["realized"] + sum(self._mark(r, price if r == root else None) for r in s["pos"])
        if day_pnl <= -c.daily_loss_lock:
            why.append(f"day P&L {day_pnl:,.0f} is at the {c.daily_loss_lock:,.0f} loss lock")
        if c.daily_profit_lock and day_pnl >= c.daily_profit_lock:
            why.append(f"day P&L {day_pnl:,.0f} reached the {c.daily_profit_lock:,.0f} profit lock")
        if stop is not None and price is not None:
            risk = abs(price - stop) * abs(target) * POINT_VALUE.get(root, 0) + 2 * abs(target) * c.commission_side
            room = s["eod_balance"] + day_pnl - s["threshold"]
            if room - risk < c.cushion:
                why.append(f"a stop-out (-${risk:,.0f}) would leave ${room - risk:,.0f} above the drawdown threshold (cushion ${c.cushion:,.0f})")
        return (not why, why, kind)

    # ── TradersPost ────────────────────────────────────────────────────────
    def traderspost_payload(self, a: dict) -> dict:
        root = str(a["sym"]).upper()
        target = 0 if a.get("action") == "flat" else int(a.get("target", 0))
        if target == 0:
            return {"ticker": self.cfg.symbols[root], "action": "exit", "sentiment": "flat"}
        body = {"ticker": self.cfg.symbols[root], "action": "buy" if target > 0 else "sell",
                "sentiment": "long" if target > 0 else "short", "quantity": abs(target), "orderType": "market"}
        if a.get("stop") is not None:
            body["stopLoss"] = {"type": "stop", "stopPrice": a["stop"]}
        if a.get("tp") is not None:
            body["takeProfit"] = {"limitPrice": a["tp"]}
        return body

    def _send(self, body: dict) -> str:
        if not self.live:
            return "dry-run"
        url = os.environ["TRADERSPOST_WEBHOOK_URL"]
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return f"sent {r.status}"

    def _log(self, rec: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def handle(self, a: dict) -> dict:
        with self.lock:
            self._roll_day()
            ok, why, kind = self.check(a)
            rec = {"at": self.now().isoformat(timespec="seconds"), "alert": a, "kind": kind,
                   "verdict": "PASS" if ok else "BLOCK", "reasons": why}
            if ok:
                body = self.traderspost_payload(a)
                try:
                    rec["sent"], rec["order"] = self._send(body), body
                    root = str(a["sym"]).upper()
                    self._apply_fill(root, 0 if a.get("action") == "flat" else int(a.get("target", 0)), a.get("price"))
                except Exception as e:  # logged; an entry is never re-sent, a flat-by exit is retried every 15 s
                    rec["verdict"], rec["error"] = "ERROR", str(e)
            day_pnl = self.state["realized"]
            if day_pnl <= -self.cfg.daily_loss_lock and not self.state.get("locked"):
                self.state["locked"] = f"realized {day_pnl:,.0f} hit the loss lock"
            self._save()
            self._log(rec)
            return rec

    def flatten_if_due(self) -> list[dict]:
        out = []
        if self.now().time() >= hm(self.cfg.flat_by) and self.state.get("pos"):
            for root in list(self.state["pos"]):
                out.append(self.handle({"acct": self.cfg.account, "sym": root, "action": "flat", "target": 0, "source": "governor flat-by"}))
        return out


def serve(gov: Governor, host: str, port: int) -> None:
    token = os.environ.get("GOVERNOR_TOKEN")
    if not token:
        raise SystemExit("set GOVERNOR_TOKEN to a long random string first")

    class H(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._reply(400, {"error": "body is not JSON"})
            if self.path == f"/tv/{token}":
                return self._reply(200, gov.handle(body))
            if self.path == f"/balance/{token}":
                with gov.lock:
                    return self._reply(200, gov.end_of_day(float(body["balance"])))
            self._reply(404, {"error": "not found"})

        def do_GET(self):
            if self.path == f"/status/{token}":
                return self._reply(200, gov.state)
            self._reply(404, {"error": "not found"})

        def log_message(self, *args):  # keep the token out of stdout logs
            pass

    def ticker():
        while True:
            try:
                gov.flatten_if_due()
            except Exception as e:
                print("flatten check failed:", e)
            _time.sleep(15)

    threading.Thread(target=ticker, daemon=True).start()
    print(f"governor on {host}:{port}  mode={'LIVE' if gov.live else 'dry-run'}  account={gov.cfg.account}")
    ThreadingHTTPServer((host, port), H).serve_forever()


def load_config(path: str | None) -> Config:
    if not path:
        return Config()
    raw = json.loads(Path(path).read_text())
    return Config(**{k: v for k, v in raw.items() if not k.startswith("_")})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--live", action="store_true", help="forward passed orders to TradersPost")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--check", help="check one alert JSON and print the verdict (nothing is sent)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.live and not os.environ.get("TRADERSPOST_WEBHOOK_URL"):
        raise SystemExit("--live needs TRADERSPOST_WEBHOOK_URL")
    if a.check:
        g = Governor(cfg)
        g._roll_day()
        ok, why, kind = g.check(json.loads(a.check))
        print(json.dumps({"verdict": "PASS" if ok else "BLOCK", "kind": kind, "reasons": why,
                          "order": g.traderspost_payload(json.loads(a.check)) if ok else None}, indent=2))
        return
    serve(Governor(cfg, live=a.live), a.host, a.port)


if __name__ == "__main__":
    main()
