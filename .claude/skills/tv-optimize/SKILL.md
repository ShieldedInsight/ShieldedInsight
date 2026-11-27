---
name: tv-optimize
description: >-
  Runs a strategy optimization in TradingView through the TruePath TV
  Optimizer (Chrome extension + tv-optimizer MCP server): reads the
  strategy's inputs, sets each candidate, exports the Strategy Tester report,
  scores it (in-sample vs out-of-sample, overnight holds, fragility, Tradeify
  pass / payout simulation) and picks settings on in-sample data only. Use
  when the user says "optimize", "run the optimizer", "test these settings in
  TradingView", "sweep the inputs", "backtest variants", or "tv-optimize".
argument-hint: "[strategy name] [what to vary]"
---

# tv-optimize

Needs the `tv-optimizer` MCP server (tools `tv_*`) and the extension
connected to an open TradingView chart. Setup: `tools/tv-optimizer/README.md`.
If `tv_status` says not connected, walk the user through the README instead of
guessing.

## The rule that matters

An optimizer that hunts for the best number finds curve fits. In this repo's
own research, MA Cross RTH looked great on one year and lost money on the next
50 sessions, and stacking filters chosen in-sample did worse out-of-sample
than no filter. So:

1. **Choose on in-sample only.** Rank candidates by `inSample` and
   `propInSample`. Do not look at `outOfSample` until the shortlist is fixed.
2. **Prefer plateaus to peaks.** A setting whose neighbours score about the
   same beats a lone best value.
3. **Few, meaningful runs.** At most ~30 runs per session, varying 1–3 inputs
   over ranges the user agrees to. No input gets a value just because it scored
   best once.
4. **Stop on warnings.** Overnight holds, under 100 positions, no in-sample
   trades, or the 10 best trades exceeding the net: report them before going on.
5. **The verdict is out-of-sample:** profit factor ≥ 1.3, positive per-trade
   result, at least 100 out-of-sample positions, and `propOutOfSample` no worse
   than the baseline's. Otherwise say plainly that nothing beat the baseline.

## Steps

1. `tv_status`. Confirm the chart's symbol and timeframe with the user, and
   that Deep Backtesting is on with a range from 2019 (or as far back as the
   data goes); the split date (default 2026-01-01) must leave years in-sample.
2. `tv_get_inputs` with the strategy's legend name. Show the inputs, agree on
   1–3 to vary and their ranges, and the Tradeify plan for scoring.
3. Baseline: `tv_export_and_score` with `label: "baseline"`. Read the warnings.
4. For each candidate: `tv_set_inputs` (only the inputs that change), then
   `tv_export_and_score` with a label naming the values (e.g. `risk400-2R`).
   If an input is reported in `failed`, stop and fix it (exact label from
   `tv_get_inputs`) before running more.
5. `tv_runs`: build the table on in-sample columns, pick the shortlist (≤ 3)
   by in-sample per-trade result, profit factor, t-stat and `propInSample`
   pass / payout rates, preferring plateaus.
6. Only now read the shortlist's `outOfSample` and `propOutOfSample`. Apply
   the verdict rule. Restore the winning (or baseline) inputs with
   `tv_set_inputs`.
7. Report: the table, the shortlist, the out-of-sample verdict, and what was
   NOT tested. Results are history on TradingView's data, not a promise.

## When TradingView changes its page

If a tool fails with "not found": `tv_inspect` (within `legend`, `dialog` or
`tester`, with `text` such as "Export" or "Inputs") to find the element, then
`tv_set_selector` for the named target (`legendSettings`, `dialog`,
`dialogOk`, `inputsTab`, `tester`, `exportButton`, `exportMenuXlsx`, `busy`)
and retry. `tv_click` handles one-off pop-ups. Tell the user which selector was
overridden so the extension's defaults can be updated.

## Never

Never changes account, broker or alert settings, never places orders, never
enables live mode on a strategy, never runs on a chart the user did not
confirm. If the export lands somewhere other than ~/Downloads, the user sets
`TVO_DOWNLOADS` in the MCP server config.
