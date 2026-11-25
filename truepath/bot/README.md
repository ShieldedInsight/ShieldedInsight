# TruePath bot

```
TradingView (KeyLevel Builder v2, 1 MNQ)  --alert-->  governor.py  --PASS-->  TradersPost  -->  prop account
                                                          |
                                                     BLOCK + log
```

The strategy stays in TradingView, where it was built and tested. The **governor** checks every alert against your prop rules before anything reaches the broker:

| Check | Entries | Exits |
|---|---|---|
| Account tag and symbol | block | block |
| Entry window (09:30–15:30 ET) and news blackouts | block | always pass |
| Must carry a stop | block | — |
| Contract limit and trades per day | block | — |
| Daily loss lock: estimated closed + open P&L ($600 by default) | block | — |
| A stop-out would land within $250 of the EOD trailing threshold | block | — |
| Flat by 15:55 ET | — | the governor sends the exit itself |

It runs in dry-run mode by default and logs every verdict to `trader/state/governor_log.jsonl`. Nothing is sent until you start it with `--live`.

## 1. Gate: prove the strategy before automating it

Nothing I could rebuild here showed an edge on fresh data:

| Strategy | Data | Result |
|---|---|---|
| MA Cross RTH (Notion #1) | MNQ 5m, Sep 28 – Nov 25 2026, **after** its test period | 727 trades, PF 0.72, t −2.5. It still loses at zero cost. |
| Late-day momentum, 3 variants decided in advance | MNQ/MES 1h, 2 years, year 2 untouched | The variant picked on year 1 had PF 1.14 and t 0.4 on year 2. |
| ORB v1 / v2 (fixed timezone) | 5m, 60 days | Profit factor 0.8–1.4 on MES/MNQ; ES and NQ had too few trades to judge. |

KeyLevel Builder v2 has the best evidence (346 trades, t 3.74, 11 of 11 months profitable), but all of it comes from 2026 data the settings were tuned on. Before going live:

1. Run the **2019+ Deep Backtest** on the exact tested settings, and record the 8 condition selections in Notion.
2. Export *List of trades* from the Strategy Tester and run it through the prop simulator:

   ```bash
   python truepath/bot/prop.py --tv-csv "List of trades.csv"          # 50K, $2,000 EOD trail
   ```

3. Go live only if the out-of-sample panel (2024+) holds **PF ≥ 1.3**, and the Monte Carlo shows **payout ≥ 70%** and **bust ≤ 15%**.

## 2. Patch the alerts

Apply `KL_BUILDER_PATCH.md`. It adds `price` and `tp` to entries and a `flat` message to every exit fill, and limits the bot to 1 contract.

## 3. Run the governor

The governor needs a public HTTPS address so TradingView can reach it, such as a small VPS behind Caddy or a container host. It needs Python 3.10+ and nothing else.

```bash
cp trader/governor.example.json trader/governor.json        # set your rules
export GOVERNOR_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python truepath/bot/governor.py --config trader/governor.json               # dry run: watch the log for a week
export TRADERSPOST_WEBHOOK_URL="https://webhooks.traderspost.io/..."          # from your TradersPost strategy
python truepath/bot/governor.py --config trader/governor.json --live
```

Endpoints (all under the secret token):

- `POST /tv/<token>`: TradingView alerts.
- `POST /balance/<token>`: post `{"balance": 50420}` after the close. This is your broker's end-of-day balance, which the trailing threshold is based on. Without it, the governor uses its own estimate.
- `GET /status/<token>`: current state.

To check one alert without running the server:

```bash
python truepath/bot/governor.py --config trader/governor.json --check '{"acct":"TP-01","sym":"MNQ","action":"buy","target":1,"stop":21000,"tp":21120,"price":21050}'
```

## 4. TradersPost

- Connect the strategy to a **paper** account first. Confirm that one buy, one sell and one exit reach the broker with the stop and target attached before switching to the funded account.
- The governor sends `{"ticker","action":"buy|sell|exit","sentiment","quantity","orderType":"market","stopLoss":{"type":"stop","stopPrice"},"takeProfit":{"limitPrice"}}`. Check these fields against TradersPost's current webhook docs and your strategy settings, including whether reversals are allowed.

## Before going live, check these yourself

- **Your prop firm's rules on automation and trade copiers.** Some firms restrict fully automated trading.
- **The trail, where it locks, the daily loss limit and the payout minimums.** Pass the right values in `governor.json` and to `prop.py`.
- **The broker is the source of truth.** The governor's intraday P&L is an estimate from alert prices. Post the real balance every day.

## Files

| File | What it does |
|---|---|
| `governor.py` | alert gate, TradersPost forwarder, 15:55 flatten |
| `prop.py` | EOD-trailing account simulator and 10,000-run Monte Carlo payout and bust odds |
| `engine.py` | MA Cross RTH replay with TradingView fill rules |
| `research.py` | the late-day momentum test |
| `tests/test_governor.py` | governor scenarios: `python truepath/bot/tests/test_governor.py` |
