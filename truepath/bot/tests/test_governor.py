"""Scenario tests for the prop governor (dry run, fake clock, temp state)."""
import sys, tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bot.governor import Config, Governor, NY  # noqa: E402


def gov(clock, **kw):
    d = tempfile.mkdtemp()
    cfg = Config(state_file=f"{d}/s.json", log_file=f"{d}/l.jsonl", **kw)
    g = Governor(cfg, now=lambda: clock[0])
    g.state_path, g.log_path = Path(cfg.state_file), Path(cfg.log_file)
    g.state = g._load()
    return g


def at(h, m, day=24):
    return datetime(2026, 11, day, h, m, tzinfo=NY)


def alert(action, target, price, stop=None):
    return {"acct": "TP-01", "sym": "MNQ", "action": action, "target": target, "price": price, "stop": stop}


def test_entry_passes_and_exit_always_passes():
    clk = [at(10, 0)]
    g = gov(clk)
    r = g.handle(alert("buy", 1, 21000, 20950))
    assert r["verdict"] == "PASS" and r["order"]["action"] == "buy" and r["order"]["stopLoss"]["stopPrice"] == 20950
    clk[0] = at(17, 0)  # after hours: an exit still goes through
    assert g.handle(alert("flat", 0, 21010))["verdict"] == "PASS"


def test_blocks():
    clk = [at(9, 15)]
    g = gov(clk)
    assert "outside the entry window" in " ".join(g.handle(alert("buy", 1, 21000, 20950))["reasons"])
    clk[0] = at(10, 0)
    assert "no stop" in " ".join(g.handle(alert("buy", 1, 21000))["reasons"])
    assert "contract limit" in " ".join(g.handle(alert("buy", 3, 21000, 20950))["reasons"])


def test_loss_lock_after_losses():
    clk = [at(10, 0)]
    g = gov(clk, daily_loss_lock=300)
    for i in range(2):
        g.handle(alert("buy", 2, 21000, 20900))
        g.handle(alert("flat", 0, 20920))       # -160 pts x $2 x 2 ... = -$320 + fees
    r = g.handle(alert("buy", 1, 21000, 20950))
    assert r["verdict"] == "BLOCK" and any("lock" in x for x in r["reasons"])


def test_trailing_room():
    clk = [at(10, 0)]
    g = gov(clk)
    g.end_of_day(48_300)   # $300 above a $48,000 threshold
    r = g.handle(alert("buy", 2, 21000, 20950))   # risk $200 + fees -> leaves < $250 cushion
    assert r["verdict"] == "BLOCK" and "drawdown threshold" in " ".join(r["reasons"])


def test_threshold_trails_then_locks():
    clk = [at(10, 0)]
    g = gov(clk)
    assert g.end_of_day(51_000)["threshold"] == 49_000
    assert g.end_of_day(53_000)["threshold"] == 50_100   # locked at start + $100
    assert g.end_of_day(52_000)["threshold"] == 50_100   # never moves down


def test_flat_by():
    clk = [at(15, 0)]
    g = gov(clk)
    g.handle(alert("sell", -1, 21000, 21050))
    clk[0] = at(15, 56)
    out = g.flatten_if_due()
    assert out and out[0]["order"]["action"] == "exit" and not g.state["pos"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
