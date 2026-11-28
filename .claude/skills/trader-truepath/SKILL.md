---
name: trader-truepath
description: >-
  TruePath Bot. Runs and tracks the automated opening-range breakout bot for
  MNQ / MES futures on a Tradeify prop account. Builds today's order after
  10:00 ET (range 09:00–10:00, VIX-direction side, one bracket stop order,
  stop at the other side, 3R target, flat 15:55, whole-contract sizing), shows
  the TradersPost webhook JSON the TradingView bot sends, tracks the
  evaluation and the funded account (trailing floor, room, target, 40%
  consistency, winning days toward a Select Flex payout), and re-tests the
  edge on fresh Yahoo data with a pass / payout simulation. Use when the user
  says "run the bot", "today's ORB", "TruePath bot", "what's the plan for
  MNQ", "log today's P&L", "am I passing", "can I take a payout", "check the
  floor", "re-test the strategy", "set up the bot", or "automate TruePath".
argument-hint: "[plan | account | backtest]"
---

# trader-truepath

The TruePath Bot trades ONE rule on futures, the only design that held up when
168,064 variants were tested on 2.4 years of ES and NQ data (in-sample
2024–25, out-of-sample 2026, costs included):

1. **Range:** high and low of 09:00–10:00 ET.
2. **Side:** VIX at 10:00 below yesterday's close → long only; above → short only.
3. **Entry:** one stop order at the range high (long) or low (short), live 10:00–15:00 ET.
4. **Stop:** the other side of the range. **Target:** 3R. **Flat:** 15:55 ET.
5. **Size:** contracts = risk ÷ (range × point value + costs), rounded down; skip the day at 0.

Execution is `TruePath_Bot_v1.pine` on a TradingView 5-minute MNQ1! chart,
sending webhook alerts to a bridge (TradersPost or PickMyTrade) connected to
the Tradeify (Tradovate) account. This skill is the cockpit around it: it
places nothing.

`${CLAUDE_SKILL_DIR}` below is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/truepath.py" plan                       # MNQ order for today (after 10:00 ET)
python3 "${CLAUDE_SKILL_DIR}/truepath.py" plan --symbols MNQ,MES
python3 "${CLAUDE_SKILL_DIR}/truepath.py" account init --plan select50 --phase eval
python3 "${CLAUDE_SKILL_DIR}/truepath.py" account log --pnl 230      # today's closed P&L from the broker
python3 "${CLAUDE_SKILL_DIR}/truepath.py" account show
python3 "${CLAUDE_SKILL_DIR}/truepath.py" account funded             # after passing
python3 "${CLAUDE_SKILL_DIR}/truepath.py" account payout --amount 900
python3 "${CLAUDE_SKILL_DIR}/truepath.py" backtest                   # re-test on fresh Yahoo data
```

Plans: `select50` (default), `select100`, `growth50`, `growth100`. Default risk:
MNQ $500, MES $300 (`--risk` overrides). Writes `trader/truepath/plan-<date>.json`
and `trader/truepath/account.json`.

## What the evidence says (tell the user plainly)

| Setup, VIX filter on, Select 50K sim | Passed | Failed | Unfinished | Median days to pass | Reached a payout |
| --- | --- | --- | --- | --- | --- |
| MNQ $500 only (default) | 83% | 0% | 17% | 72 | 77% |
| MES $300 only | 80% | 0% | 20% | 118 | 75% |
| MES $400 + MNQ $500 | 62% | 38% | 0% | 39 | 52% |

- Per trade: ES +4.3 pts (PF 1.40, all half-years positive); NQ +20.9 pts
  in-sample (PF 1.42), +16.5 out-of-sample (PF 1.25).
- It is SLOW: a small edge at a safe size takes 3–6 months to pass. Bigger size
  passes faster and fails far more often. Never raise risk to hurry it.
- Rejected after testing: MA Cross RTH (SMA 7) lost on 50 new sessions even
  before costs; fades, tight stops and close-confirmed entries lose; stacking
  filters (MAs, momentum, Donchian, pivots, volume, VIX term structure) was
  curve-fitting.
- Limits: hourly test bars (the tested range starts 30 min before the cash
  open); Yahoo continuous futures; Tradeify rules from third-party summaries.

## Cash account (Webull) — dynamic sizing, bot v1.2 default

`TruePath_Bot_v1.pine` v1.2 defaults to a $10,000 cash account with no prop rules
(Account Plan = Off, Sizing Mode = "% of equity · by grade"):

- Risk 2% of equity on a B setup, 3% on an A / A+ setup; contracts = risk ÷ (range ×
  point value + costs), rounded down, 1–5; skip the day at 0.
- Grade at 10:00, one point each: side agrees with yesterday's close vs its 20-day SMA;
  today's range ≤ median of the last 20; VIX prior close < its 20-day average; not an
  FOMC day, first Friday (NFP) or (MCL) Wednesday. A+ = 4, A = 3, B = 0–2.
- Day-margin cap: contracts × Webull day margin ≤ 50% of equity (MNQ $161.08, MES
  $100.10, MGC $540.54, MCL $307.18 as published Nov 2026, 09:00–16:15 ET).
- Live: set "Live Account Equity" to the broker balance and update it weekly.

$10,000 test, Jul 2024 – Nov 2026, MNQ + MES: +147%/yr, max drawdown −21%, worst day
−5.7%; 2026 alone from $10,000: +82%, drawdown −13%. That test used the candle side
rule and took a trade only when the range's FIRST break was on the chosen side; the bot
still uses the VIX side and a resting stop order, which lost money in the same test
(−51%). Align the bot's entry before trading it live. The grade did not sort trades
reliably out of sample; the 3% step is a modest bet, not an edge. MCL had no edge.

## Forward test (Nov 30 – Dec 11, 2026)

`forward.py` paper-trades the frozen rule (TP-ORB-forward-3: 09:00–10:00 range, candle side, first
break must be on that side, stop at the other edge, 3R, flat 15:55) on a simulated Tradeify Select 50K
account: **MES $400 risk (about 3 contracts) in the account, skipping days whose range is wider than 1.5× its 20-session
median**; MNQ $500 (no filter) logged as a shadow. A scheduled task runs `python3 forward.py settle`
after each close; it settles any finished session not yet in `trader/truepath/forward/ledger.csv`
from Yahoo 5-minute bars, updates `account.json` and the report `README.md`. Never edit the rules
during the window.

Research behind it (Nov 28, hourly NQ/ES Jul 2024 – Nov 25 2026, all data, 2026 included):
- Candidates: ORB with candle side avg +0.18 R (NQ) / +0.20 R (ES), positive in H2 2024, 2025 and
  2026; two-sided ORB weaker; noise-area momentum and RSI(2) reversal failed.
- Refinement adopted only if it beat the plain rule in all three periods: the 1.5× range filter
  passed on ES (+0.243 R, PF 1.58) but not on NQ (worse in H2 2024), so MES only.
- Select 50K simulation from every start day, MES filtered: $300 91% passed / 0% failed (median 116
  sessions); $400 84% / 12% (57; 2026 starts 89% / 0%), chosen to add contracts; $500 80% / 20% (43); MNQ $500 77% / 11% (61); MNQ $500 + MES $300 80% / 18% (49).
- With 2026 used to choose, the forward window is the only test on unseen data.

## Second leg: gold (MGC) — experimental

Same range (09:00–10:00 ET) on MGC, side = the direction the 09:00–10:00 hour
closed, entries until 12:00, flat 13:00, risk $250. It is uncorrelated with the
MNQ leg (daily correlation 0.09) and, simulated with MNQ $500 on Select 50K,
raised payout odds from 77% to 83–85% and cut the median time to the first
payout from ~114 to ~84 sessions — but 13–15% of evaluations failed (MNQ alone: 0%).

**It is not confirmed.** Yahoo serves two versions of gold's 2024–25 history: on
one the rule made +1.2 pts/trade (PF 1.23), on the other it lost (−0.49, PF 0.93).
Both agree on 2026 (≈ +2.4 pts, PF ≈ 1.3, 144 trades). `backtest` now downloads
twice and prints a WARNING when the copies differ. Do not add MGC to a paid
evaluation until a TradingView Deep Backtest on MGC1! from 2019 (use
`/tv-optimize`) shows profit factor ≥ 1.2 in-sample and out-of-sample. Until
then: `plan --symbols MNQ,MGC` and `backtest --symbols MNQ,MGC` are opt-in.

Rejected as second strategies (tested once each, Nov 2026): last-hour momentum
(Gao, Han, Li & Zhou 2018) lost on ES in both periods and was inconsistent on NQ;
the overnight gap fade worked in 2024–25 and failed in 2026.

## Steps

**Daily (before 15:00 ET):**
1. After 10:00 ET: `plan`. Tell the user the range, the side, the order (or
   why there is none), and the status. Compare with the TradingView panel; if
   they differ, the chart wins (Yahoo is a delayed proxy).
2. After the close: `account log --pnl <broker's closed P&L for the day>`, then
   `account show`. Report room to the floor, progress, consistency or winning
   days, and payout readiness.

**Setup (once):** walk the user through `setup.md` in this folder: TradingView
chart and alert, bridge, Tradeify, paper run first.

**Monthly:** `backtest`. If MNQ's per-trade result since the split date turns
negative over 60+ trades, tell the user to pause the bot.

## What it never does

It never places, changes or cancels an order. It never raises risk to pass
faster. It never calls a simulation a promise: it is history, on free data.

## Safety

- Education and tooling, not financial advice. Futures can lose more than the stop in a fast market or a gap.
- Paper-trade the bot (TradersPost paper, or Tradovate sim) for at least 20 sessions before a paid evaluation.
- Automated trading on Tradeify requires that the strategy is the user's own and is not used across firms;
  Tradeify may ask for proof. Confirm the current policy with Tradeify before going live.
- Keys and webhook URLs live in the bridge and TradingView, never in chat or in these files.
