# TruePath_ORB_v1

An opening-range breakout for index futures (ES, NQ, MES, MNQ) on a 5-minute chart. It follows the same rules as the `trader-entry` and `trader-exit` skills, adds the short side, and adds prop-firm guards.

| Rule | Default |
|---|---|
| Opening range | 9:30–9:45 ET (15 min) |
| Entry | first 5m bar that **closes** above the range high (long) or below the range low (short), 9:45–11:30 ET |
| Filter | close on the breakout side of session VWAP (EMA and volume filters off by default) |
| Stop | range midpoint (or the opposite side, or ATR × 1.5) |
| Target | 2R |
| Exit | flat by 15:55 ET |
| Risk | skip any trade risking more than $500/contract; halt the day at −$1,000 |
| Costs | $1.55 per side ($3.10 round trip), no slippage |

## Files

- `TruePath_ORB_v1.pine`: Pine Script v6 strategy. Paste it into TradingView's Pine Editor and add it to a 5m ES1! or NQ1! chart.
- `orb_backtest.py`: replays the same rules on OpenBB data, grid-searches stop mode, reward, VWAP filter, entry cutoff and first-break-only on in-sample days, re-checks the top 5 on out-of-sample days, and scores each for a prop firm. Writes `trader/truepath_orb_backtest.json`.

## Run the backtest

```bash
pip install openbb-core openbb-equity openbb-yfinance   # or install core/equity from a local OpenBB clone
python truepath/orb_backtest.py                         # ES=F NQ=F MES=F MNQ=F, 50K account
python truepath/orb_backtest.py --account 100000 --symbols NQ=F MNQ=F
```

The run needs network access to `query1.finance.yahoo.com` and `query2.finance.yahoo.com`. Yahoo only serves 5-minute bars for about the last 60 days. For the one-year check, use TradingView's Strategy Tester.

## Prop score (0–100)

| Part | Points | What earns full marks |
|---|---|---|
| Edge | 30 | profit factor of 2.0 or more |
| Daily loss | 25 | no day past the EOD limit ($2K on 50K, $3K on 100K), and a small worst day |
| Drawdown | 20 | small drawdown relative to the EOD limit |
| Consistency | 15 | best day at or under 30% of total profit |
| Sample | 10 | 40 trades or more |

Any result with a profit factor of 1.5 or less is marked "fails PF > 1.5", whatever its score.

# TruePath_ORB_v2: confirmed breakout, order at the level

v2 keeps v1's opening range, midpoint stop, 2R target and prop-firm guards, and changes how a trade starts:

1. **Confirm the breakout.** The bar that closes outside the range must show momentum: RSI(14) ≥ 60 for longs (≤ 40 for shorts), and a close in the top 60% of the bar for longs (bottom 60% for shorts). A volume check is optional: the breakout bar's volume must be at least X × the average opening-range bar. It's off by default because it made results worse in testing.
2. **Order at the level.** Once a breakout is confirmed, a buy limit rests at the range high (a sell limit at the range low for shorts) for 6 bars. The trade only fills if price comes back to retest the level. The stop is the range midpoint and the target is 2R from the level. "At Close (market)" is still available as an option.

Unconfirmed breaks are marked on the chart with a grey ×.

```bash
python truepath/orb_backtest.py --version 2     # writes trader/truepath_orb_v2_backtest.json
```

## v2 results, OpenBB 5m, 2026-09-28 → 2026-11-25 (≈52 sessions, 50K account)

These were re-run on 2026-11-25 after fixing a timezone bug: the first run read New York bar times as UTC, so every earlier v1/v2 number was measured 4–5 hours off and is invalid.

| Contract | Trades | Net | Profit factor | Prop score |
|---|---|---|---|---|
| ES | 11 | +$2,491 | 2.47 | 72, workable |
| MES | 27 | +$433 | 1.36 | 54, fails |
| MNQ | 28 | −$613 | 0.82 | 35, fails |
| NQ | 0 | — | — | the $500 cap blocks every trade |

None of these is a usable result. ES had 11 trades. ES and MES are the same market, yet they gave very different results, which means the $500 cap is choosing which days get traded. MNQ lost. See `bot/README.md` for the rest of the testing and the plan.
