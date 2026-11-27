# TruePath_VWAP_Revert_v1: TradingView Deep Backtest review (MNQ1! 5m, May 2019 to Nov 2026)

Core settings (k = 2.5, stop 1.5σ, 24-bar time stop, edge 3× cost, 10:00–15:00, all filters off), 1 contract, $1.55/side + 2 ticks.

| Period | Trades | Net | PF | t |
|---|---|---|---|---|
| In-sample 2019–22 | 841 | −$7,748 | 0.78 | −2.79 |
| Out-of-sample 2023–26 | 879 | −$3,319 | 0.93 | −0.82 |
| All | 1,720 | −$11,068 | 0.87 | — |

- **Lost in 7 of 8 years.** The only positive year was 2025, at +$1,148 and PF 1.09.
- **In-sample exits:** 479 stops (−$33,608) against 242 VWAP targets (+$24,558), 82 time exits (+$1,183) and 38 end-of-day exits (+$120). A 2.5σ stretch on MNQ keeps going more often than it comes back to VWAP.
- **Filter screen, in-sample, tagged from daily NQ data:** F5 trend alignment PF 0.75, F7 volatility band 0.81, F5+F7 0.76, F6 midday 0.78. None gets close to 1.
- **Trading the opposite direction doesn't work either.** In-sample costs were about $4,300, so the fade lost only about $3,400 before costs. A breakout version would make about that much before costs and still be negative after them.

**Verdict:** the core fails in-sample, so the out-of-sample test can't save it. Retire it, unless F1 (trend-day veto) or F3 (reversal bar), the two filters aimed at runaway stretches, lift in-sample PF to at least 1.1 when rerun in TradingView.
