---
name: trader-review
description: >-
  Trade Review. Reviews the TruePath Bot's live and paper trades from the
  screenshot journal the TruePath TV Optimizer extension saves (a chart
  screenshot when each trade opens, with entry, stop and target, and one when it
  hits the target, the stop or the end of day). Pairs each trade's screenshots
  with its numbers, scores the results against the backtest, looks at every
  loser and a sample of winners with a fixed checklist, tags them, writes a
  weekly review, and turns repeated patterns into ideas to TEST, never into live
  rule changes. Use when the user says "review my trades", "trade journal",
  "look at the screenshots", "what can the bot learn", "weekly review", "why
  did that trade lose", or "improve the bot from its trades".
argument-hint: "[since YYYY-MM-DD]"
---

# trader-review

The bot does not change itself. Screenshots make each trade easy to inspect, but
a handful of trades is mostly noise: the backtest edge is about +0.15–0.20 R per
trade with a 54% win rate, so even 20 trades can lose money by chance. This skill
turns the journal into tagged observations and testable ideas; an idea reaches the
bot only after it passes `/tv-optimize` (chosen on in-sample data, confirmed
out-of-sample) and the user approves the change.

## Where the journal is

- Screenshots + JSON: `~/Downloads/TruePath-Journal/<date>/<SYM>_<OPEN|CLOSE>_<hhmmss ET>.png/.json`
  (saved by the extension when the bot's Journal Mode copy raises a `TPJ|` pop-up).
- Notes and tags: `~/.tv-optimizer/journal-notes.jsonl`.
- With the `tv-optimizer` MCP server: `tv_journal` (trades + summary),
  `tv_journal_image` (look at a screenshot), `tv_journal_note` (save tags).
  Without it, read the JSON files and open the PNGs with the Read tool.

## Steps

1. **Load** `tv_journal` (or the folder) since the last review (default: 7 days).
   Report open trades with no CLOSE (a missed screenshot or a position still on).
2. **Score** against the backtest: trades, win rate, average R, P&L, by symbol,
   grade, side and outcome. Expected: win ≈ 54%, avg R ≈ +0.15, about 1 trade a day
   per market. Say plainly whether the sample is big enough to mean anything
   (under 30 trades: it is not).
3. **Check execution first** (the most common real problem): for each trade compare
   the journal entry price with the range edge, and the broker's fill if the user
   gives it. Flag slippage over 2 ticks, fills outside 10:00–15:00, trades on a side
   the rule did not allow, a CLOSE without a TARGET/STOP/EOD reason, or a missing
   screenshot.
4. **Look** at every loser's OPEN and CLOSE screenshots and at as many winners
   (the most recent). For each, answer the checklist and save it with
   `tv_journal_note` using these tags only:
   - `trend-with` / `trend-against` — price vs the visible 20-day trend
   - `wide-range` / `tight-range` — the 09:00–10:00 range vs recent days
   - `fake-break` — broke out, then closed back inside the range within 2 bars
   - `news-spike` — entry on an 08:30/10:00/14:00 release candle or a gap
   - `late-fill` — filled after 13:00
   - `chop` — price crossed the range more than twice before the fill
   - `level-near` — prior-day high/low or a round number within 0.5R of entry
   - `execution` — slippage, a missed order or a wrong size
   Describe only what is visible; do not guess at news that is not on the chart.
5. **Group** the tags: average R per tag across ALL reviewed trades (not just this
   week). A pattern is worth testing only if it appears in 15+ trades and its
   average R differs from the rest by more than 0.3 R.
6. **Turn a pattern into a rule to test**, written precisely enough for Pine (e.g.
   "skip when the range is wider than 1.5 × its 20-day median"). Hand it to
   `/tv-optimize`: Deep Backtest from 2019, decide on in-sample only, then check
   2026. Report both. If it fails out-of-sample, record it as rejected.
7. **Write** `trader/truepath/reviews/<YYYY>-W<ww>.md`: the score, execution flags,
   each trade's tags in one line, patterns building up, ideas sent to test and
   their results, and one sentence on whether anything should change. Default
   answer: no change.

## Never

- Never change the bot's inputs, sizing or rules from the journal alone, and never
  raise size after a winning week or cut the strategy after a losing one; the
  monthly `/trader-truepath backtest` check decides pauses (MNQ's per-trade result
  since the split turning negative over 60+ trades).
- Never treat a screenshot as proof of why a trade won or lost.
- Never place, change or cancel an order.
