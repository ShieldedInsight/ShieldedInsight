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
