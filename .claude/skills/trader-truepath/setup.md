# TruePath Bot — setup

The bot is three pieces: TradingView decides, a bridge forwards, Tradovate (the
platform behind your Tradeify account) executes.

```
TradingView: TruePath_Bot_v1 on MNQ1! 5m ──alert() JSON──▶ bridge (TradersPost / PickMyTrade) ──▶ Tradovate ──▶ Tradeify account
                                                                                                   ▲
trader-truepath (this skill): daily plan, P&L log, floor / payout tracking, monthly re-test ───────┘ (reads only)
```

## 1. TradingView (signal)

1. A plan with webhook alerts (TradingView Essential or higher).
2. Chart: `CME_MINI:MNQ1!`, 5-minute, **extended hours ON** (the range starts at 09:00 ET).
3. Pine Editor → paste `TruePath_Bot_v1.pine` (in this folder) → Add to chart.
4. Inputs: Account Plan = your Tradeify plan · Account Phase = Evaluation ·
   Risk = 0 (auto: MNQ $500) · VIX Direction Filter = on · Live Mode = **off**.
5. Check the panel: range, VIX side, contracts. Run the Strategy Tester and
   compare with the evidence table in `SKILL.md`.

## 2. Bridge (forwarding)

TradersPost (or PickMyTrade) connects to Tradovate with your Tradeify login.

1. Create a strategy in the bridge, connect the Tradeify / Tradovate account,
   start with the **paper** (simulated) connection.
2. Map the ticker: the bot sends `"ticker":"MNQ"` (the chart's root; override
   with the Bridge Ticker input). Point it at the front-month contract.
3. Bridge risk settings: max position 2 contracts, flatten at session end.
4. Check that the bridge accepts a stop entry with an attached stop-loss and
   take-profit in this shape (TradersPost's documented JSON format; confirm in
   their docs before going live):

```json
{"ticker":"MNQ","action":"sell","orderType":"stop","stopPrice":25027.50,"quantity":1,
 "stopLoss":{"type":"stop","stopPrice":25477.25},"takeProfit":{"limitPrice":23678.25}}
```

The bot also sends `{"ticker":"MNQ","action":"cancel"}` at 15:00 if the order
did not trigger, and `{"ticker":"MNQ","action":"exit"}` at 15:55 or when the
prop guard trips.

## 3. TradingView alert (the switch)

1. Bot input Live Mode = **on**.
2. Create Alert → Condition: `TruePath_Bot_v1` → **"alert() function calls only"**.
3. Notifications → Webhook URL = the bridge's URL for this strategy. Leave the
   message box empty (the bot writes the JSON). Expiration: open-ended.
4. In live mode the bot only trades when the VIX gives one side, so it sends a
   single bracket order — no one-cancels-other needed.

## 3b. Trade journal screenshots (optional, recommended)

The bot can't take screenshots itself (Pine has no such function), so a second,
order-free copy raises pop-ups that the TruePath TV Optimizer extension
(`tools/tv-optimizer`, v1.1+) turns into screenshots.

1. Add `TruePath_Bot_v1` to the same chart a second time, with the same inputs and
   **Journal Mode = on** (that copy never sends orders).
2. Create an alert on that copy: "alert() function calls only", **Show pop-up on**,
   **no webhook**. Expiration: open-ended.
3. Extension options: "Trade journal screenshots" ticked. In Chrome settings turn
   off "Ask where to save each file".
4. Keep the chart open in its own Chrome window (not minimized) during the session.
   When a trade opens and when it closes, the extension saves
   `Downloads/TruePath-Journal/<date>/<SYM>_<OPEN|CLOSE>_<time>.png` plus a JSON
   file with entry, stop, target, grade, outcome, P&L and R. The chart labels each
   entry ("LONG 2 @ … SL … TP … Grade A") and outcome ("TARGET +$712 (+2.9R)").
5. Weekly: `/trader-review`. Events appear up to one bar (5 minutes) after the
   fill, and the prices are the chart's simulated fills: compare with Webull's.

If a screenshot fails, the extension options page shows the error. If it says the
'<all_urls>' or 'activeTab' permission is required, add `"<all_urls>"` to
`host_permissions` in the extension's `manifest.json` and reload it.

## 4. Paper run (at least 20 sessions)

- Every day: `truepath.py plan` after 10:00 and compare with the panel and the
  bridge's order log. After the close: `truepath.py account log --pnl <P&L>`.
- Check fills against the backtest: entry slippage on the stop, the 15:00
  cancel, the 15:55 exit.
- Only then switch the bridge to the paid evaluation account.

## 5. Tradeify

- Confirm Tradeify's current automation policy: personal bots are reported as
  allowed (no high-frequency trading, you must own the strategy, not used
  across firms, proof may be requested).
- Verify the plan's rules (target, trailing drawdown, consistency, payout
  rules) on Tradeify's help center and set the bot's Account Plan to match, or
  use Custom.
- After passing: `truepath.py account funded`, and set the bot's Account Phase
  to Funded.
