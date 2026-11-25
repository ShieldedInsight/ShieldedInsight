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
