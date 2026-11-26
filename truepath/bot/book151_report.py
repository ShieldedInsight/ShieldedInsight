"""Turn trader/book151_results.csv into trader/book151_report.md.

Tier 1 (as asked): every test with positive expectancy per trade AND positive net P&L.
Tier 2 (what is likely real): Tier 1, plus
  - at least 30 trades,
  - t-stat of daily P&L above the multiple-testing bar (Bonferroni, one-sided 5%, over all tests),
  - positive in both halves (daily: before and after the book's Aug 2018 publication),
  - for long-biased rules, more net than buy-and-hold of the same market and timeframe.
Prop-tradeable = holds nothing overnight: only the intraday "rth" runs qualify for a Tradeify account.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
LONG_BIASED = ("0 Benchmark", "4.1 Sector momentum rotation (long only)", "4.1.2", "4.6", "6.5", "9.3")


def fmt(x, money=False):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"${x:,.0f}" if money else f"{x:,.2f}"


def table(df: pd.DataFrame) -> str:
    cols = ["strategy", "market", "tf", "mode", "trades", "net", "expectancy", "t_stat", "pf_days", "worst_day", "max_dd", "first_net", "second_net"]
    head = "| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |\n|" + "---|" * 13
    lines = [head]
    for _, r in df[cols].iterrows():
        lines.append(f"| {r.strategy} | {r.market} | {r.tf} | {r['mode']} | {int(r.trades)} | {fmt(r.net, 1)} | {fmt(r.expectancy, 1)} | "
                     f"{fmt(r.t_stat)} | {fmt(r.pf_days)} | {fmt(r.worst_day, 1)} | {fmt(r.max_dd, 1)} | {fmt(r.first_net, 1)} | {fmt(r.second_net, 1)} |")
    return "\n".join(lines)


def main() -> None:
    res = pd.read_csv(ROOT / "trader" / "book151_results.csv")
    res = res[res.get("error").isna()] if "error" in res else res
    book = res[~res.strategy.str.startswith("0 Benchmark")]
    bench = res[res.strategy.str.startswith("0 Benchmark")].set_index(["market", "tf", "mode"])["net"]
    n = len(book)
    bar = norm.ppf(1 - 0.05 / n)

    t1 = book[(book.expectancy > 0) & (book.net > 0)].copy()
    t1["bench"] = [bench.get((r.market, r.tf, r["mode"])) for _, r in t1.iterrows()]
    beats = [(not r.strategy.startswith(LONG_BIASED)) or (r.bench is None or pd.isna(r.bench) or r.net > r.bench) for _, r in t1.iterrows()]
    t2 = t1[(t1.trades >= 30) & (t1.t_stat > bar) & (t1.first_net > 0) & (t1.second_net > 0) & pd.Series(beats, index=t1.index)]
    prop = t1[t1["mode"] == "rth"]

    by_tf = book.groupby("tf").apply(lambda g: f"{(g.net > 0).sum()}/{len(g)}", include_groups=False)
    out = [
        "# 151 Trading Strategies: futures backtest (MES, MNQ, M2K, MGC)",
        "",
        "Source: Kakushadze & Serur, *151 Trading Strategies* (SSRN 3247865). Run by `truepath/bot/book151.py` on OpenBB/yfinance data.",
        "",
        "## Setup",
        "",
        "- **Prices:** full-size ES, NQ, RTY and GC continuous contracts. P&L is in micro dollars: MES $5, MNQ $2, M2K $5, MGC $10 per point, 1 contract (portfolio rules: 1 contract in total, split by weight).",
        "- **Costs and fills:** $1.55 per side plus 2 ticks of slippage. Fills at the next bar's open.",
        "- **Parameters:** the book's own examples, otherwise one value fixed before the first run. Nothing tuned.",
        "- **Timeframes:** 1d (2010 to 2026; RTY from 2017), 1h (Nov 2024 to Nov 2026), 15m and 5m (Sep 29 to Nov 25, 2026).",
        "- **Modes:** `24h` runs the rule as written, holding overnight. `rth` is flat outside 09:30–15:55 ET, the only mode a Tradeify account can trade.",
        f"- **Tests:** {n} book-strategy tests plus buy-and-hold benchmarks. Positive net by timeframe: " + ", ".join(f"{k} {v}" for k, v in by_tf.items()) + ".",
        f"- **Multiple-testing bar:** with {n} tests, luck alone produces a t-stat above 1.65 about {n * 0.05:.0f} times. A result must reach **t > {bar:.2f}** (Bonferroni, one-sided 5%) before it counts as likely real.",
        "",
        f"## Tier 2: likely real ({len(t2)})",
        "",
        "Tier 1 results that also have at least 30 trades, a t-stat above the multiple-testing bar, a profit in both halves, and (for long-biased rules) more net than buy-and-hold.",
        "",
        table(t2.sort_values("t_stat", ascending=False)) if len(t2) else "**None.** No strategy passed every check.",
        "",
        f"## Prop-tradeable: flat overnight, positive expectancy and net ({len(prop)})",
        "",
        "Intraday `rth` runs only. The 15m and 5m runs cover about 40 trading days, which is too short to separate skill from luck.",
        "",
        table(prop.sort_values("t_stat", ascending=False)) if len(prop) else "None.",
        "",
        f"## Tier 1: every result with positive expectancy and positive net P&L ({len(t1)})",
        "",
    ]
    for tf in ["1d", "1h", "15m", "5m"]:
        g = t1[t1.tf == tf].sort_values("net", ascending=False)
        out += [f"### {tf} ({len(g)})", "", table(g) if len(g) else "None.", ""]
    out += ["## Buy-and-hold benchmarks", "", table(res[res.strategy.str.startswith("0 Benchmark")].sort_values(["tf", "market", "mode"])), "",
            "## Not testable with these four futures", ""]
    nt = json.loads((ROOT / "trader" / "book151_not_testable.json").read_text())
    out += [f"- **{k}:** {v}" for k, v in nt.items()]
    (ROOT / "trader" / "book151_report.md").write_text("\n".join(out) + "\n")
    print(f"tests={n} bar={bar:.2f} tier1={len(t1)} tier2={len(t2)} prop={len(prop)}")


if __name__ == "__main__":
    main()
