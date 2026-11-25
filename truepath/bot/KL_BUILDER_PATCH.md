# KeyLevel Builder v2.0.1: alert patch for the governor

There are two changes, both to alert messages only. Signals, orders and backtest results stay the same.

**Why it's needed:** today only entries and the EOD/window close carry an `alert_message`. When a stop or a target fills in TradingView, the alert goes out empty, so the governor never learns the trade closed. The broker also never gets a take-profit order.

## 1. Replace `f_alert`

```pinescript
f_alert(string act, int target, float stp, float tp = na) =>
    '{"acct":"' + i_acctTag + '","sym":"' + syminfo.root + '","action":"' + act + '","target":' + str.tostring(target) +
     ',"price":' + str.tostring(close, format.mintick) +
     (na(stp) ? "" : ',"stop":' + str.tostring(stp, format.mintick)) +
     (na(tp) ? "" : ',"tp":' + str.tostring(tp, format.mintick)) + '}'
```

## 2. Send the target with the entry, and a "flat" on every exit fill

In the `strategy.entry(...)` call, change the `alert_message` to:

```pinescript
alert_message = f_alert(d == 1 ? "buy" : "sell", d * i_qty, pS, useTP ? (q1 > 0 ? pT1 : pTn) : na))
```

Add `alert_message = f_alert("flat", 0, na)` to each of the four `strategy.exit(...)` calls: `T1`, `T2`, `T3` and `X`. For example:

```pinescript
strategy.exit("T1" + sfx, eid, qty = q1, limit = pT1, stop = pS, comment_profit = "TP1", comment_loss = slTx, alert_message = f_alert("flat", 0, na))
```

## Limits of this patch

- **One contract only.** At 1 contract the whole position exits at TP1 or the stop, so "flat" is always correct. That's the tested setup: the Notion page notes the 50/50 split sends the whole contract to TP1. With more contracts, a partial exit would send "flat" too early. The governor's example config sets `max_contracts: 1` for this reason.
- **No breakeven or trailing stop updates.** Stop moves after entry aren't sent to the broker. At 1 contract they never act anyway, because TP1 closes the trade. Leave the trailing stop on "After TP1", not "Immediately".

## TradingView alert settings

- **Condition:** TruePath_KeyLevel_Builder_v2, *Order fills only*
- **Message:** `{{strategy.order.alert_message}}` and nothing else
- **Webhook URL:** `https://<your governor host>/tv/<GOVERNOR_TOKEN>`
