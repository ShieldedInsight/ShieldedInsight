# 151 Trading Strategies: futures backtest (MES, MNQ, M2K, MGC)

Source: Kakushadze & Serur, *151 Trading Strategies* (SSRN 3247865). Run by `truepath/bot/book151.py` on OpenBB/yfinance data.

## Setup

- **Prices:** full-size ES, NQ, RTY and GC continuous contracts. P&L is in micro dollars: MES $5, MNQ $2, M2K $5, MGC $10 per point, 1 contract (portfolio rules: 1 contract in total, split by weight).
- **Costs and fills:** $1.55 per side plus 2 ticks of slippage. Fills at the next bar's open.
- **Parameters:** the book's own examples, otherwise one value fixed before the first run. Nothing tuned.
- **Timeframes:** 1d (2010 to 2026; RTY from 2017), 1h (Nov 2024 to Nov 2026), 15m and 5m (Sep 29 to Nov 25, 2026).
- **Modes:** `24h` runs the rule as written. `tradeify` is flat during Tradeify's no-hold windows: 16:59–17:59 ET Monday to Thursday, and Friday 16:59 to the Sunday 18:00 open. On daily bars that means closing at each session's close and reopening at the 6 pm open, paying a round trip every day. `rth` (intraday only) is flat outside 09:30–15:55 ET.
- **Tests:** 849 book-strategy tests plus buy-and-hold benchmarks. Positive net by timeframe: 15m 92/231, 1d 63/156, 1h 71/231, 5m 71/231.
- **Multiple-testing bar:** with 849 tests, luck alone produces a t-stat above 1.65 about 42 times. A result must reach **t > 3.85** (Bonferroni, one-sided 5%) before it counts as likely real.

## Tier 2: likely real (0)

Tier 1 results that also have at least 30 trades, a t-stat above the multiple-testing bar, a profit in both halves, and (for long-biased rules) more net than buy-and-hold.

**None.** No strategy passed every check.

## Tradeify-tradeable: positive expectancy and net (77; 0 of them also pass Tier 2)

`tradeify` runs only. The 15m and 5m runs cover about 40 trading days, which is too short to separate skill from luck.

| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.14 Support and resistance (pivot) | MNQ | 1h | tradeify | 1293 | $21,873 | $17 | 1.92 | 1.25 | $-2,367 | $7,228 | $-178 | $22,050 |
| 3.13 Three moving averages (3/10/21) | MGC | 1h | tradeify | 1186 | $22,050 | $19 | 1.91 | 1.27 | $-2,230 | $6,618 | $9,649 | $12,401 |
| 3.12 Two moving averages (10/30) | MGC | 1h | tradeify | 878 | $24,274 | $28 | 1.87 | 1.25 | $-2,298 | $11,497 | $8,898 | $15,376 |
| 8.1 Moving averages with HP filter | MNQ | 5m | tradeify | 131 | $10,999 | $84 | 1.83 | 2.02 | $-3,080 | $3,630 | $1,983 | $9,017 |
| 3.15 Channel, breakout (Donchian 20) | MGC | 1h | tradeify | 827 | $22,306 | $27 | 1.69 | 1.22 | $-4,258 | $6,339 | $6,587 | $15,719 |
| 3.12 Two moving averages + 2% stop | MGC | 1h | tradeify | 875 | $20,926 | $24 | 1.62 | 1.21 | $-2,679 | $11,164 | $8,602 | $12,324 |
| 18.2 Neural network (MLP) | MNQ | 1d | tradeify | 365 | $27,426 | $75 | 1.61 | 1.12 | $-2,780 | $10,968 | $-2,048 | $29,473 |
| 4.1 Sector momentum rotation (long/short) | portfolio | 15m | tradeify | 178 | $3,431 | $19 | 1.47 | 1.76 | $-1,040 | $1,729 | $740 | $2,691 |
| 3.15 Channel, fade (Donchian 20) | M2K | 1h | tradeify | 886 | $5,167 | $6 | 1.40 | 1.17 | $-432 | $2,823 | $152 | $5,015 |
| 10.4 Trend following (portfolio) | portfolio | 15m | tradeify | 230 | $2,703 | $12 | 1.23 | 1.63 | $-664 | $1,167 | $756 | $1,947 |
| 3.4 Low-volatility anomaly | portfolio | 15m | tradeify | 96 | $2,607 | $27 | 1.20 | 1.61 | $-754 | $1,242 | $372 | $2,234 |
| 3.13 Three moving averages (3/10/21) | MNQ | 15m | tradeify | 316 | $6,396 | $20 | 1.14 | 1.60 | $-1,615 | $4,062 | $-875 | $7,271 |
| 3.11 Single moving average (EMA 50) | MNQ | 15m | tradeify | 342 | $7,153 | $21 | 1.12 | 1.54 | $-1,804 | $3,252 | $-1,285 | $8,438 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 15m | tradeify | 58 | $3,098 | $53 | 1.11 | 1.67 | $-974 | $1,696 | $-1,420 | $4,518 |
| 4.1.1 Rotation with MA filter | portfolio | 15m | tradeify | 143 | $2,485 | $17 | 1.06 | 1.50 | $-1,058 | $2,224 | $581 | $1,904 |
| 3.4 Low-volatility anomaly | portfolio | 5m | tradeify | 136 | $2,128 | $16 | 1.05 | 1.52 | $-789 | $1,069 | $826 | $1,302 |
| 18.2 Neural network (MLP) | MES | 1d | tradeify | 371 | $7,894 | $21 | 1.05 | 1.10 | $-943 | $6,360 | $-4,559 | $12,452 |
| 6.5 Volatility targeting (15%) | MNQ | 1d | tradeify | 1 | $17,537 | $17,537 | 1.04 | 1.06 | $-2,947 | $9,128 | $-855 | $18,392 |
| 3.12 Two moving averages + 2% stop | MNQ | 5m | tradeify | 477 | $5,757 | $12 | 1.00 | 1.42 | $-1,434 | $4,644 | $-1,534 | $7,291 |
| 3.12 Two moving averages (10/30) | MNQ | 5m | tradeify | 477 | $5,757 | $12 | 1.00 | 1.42 | $-1,434 | $4,644 | $-1,534 | $7,291 |
| 10.4 Trend following, one market | MGC | 15m | tradeify | 52 | $4,130 | $79 | 0.99 | 1.52 | $-1,996 | $1,996 | $-188 | $4,318 |
| 9.5 Skewness premium | portfolio | 1h | tradeify | 1135 | $6,316 | $6 | 0.97 | 1.12 | $-1,308 | $4,739 | $5,603 | $713 |
| 3.15 Channel, breakout (Donchian 20) | MES | 15m | tradeify | 159 | $2,661 | $17 | 0.97 | 1.50 | $-463 | $1,647 | $-1,037 | $3,698 |
| 4.1.1 Rotation with MA filter | portfolio | 5m | tradeify | 318 | $1,980 | $6 | 0.92 | 1.38 | $-584 | $1,947 | $-2,006 | $3,986 |
| 3.11 Single moving average (SMA 50) | MNQ | 15m | tradeify | 309 | $5,339 | $17 | 0.86 | 1.40 | $-2,682 | $4,064 | $-1,551 | $6,890 |
| 3.15 Channel, breakout (Donchian 20) | MES | 5m | tradeify | 384 | $2,459 | $6 | 0.86 | 1.43 | $-1,267 | $2,455 | $-1,248 | $3,707 |
| 3.1 Price momentum (12-1, time series) | MNQ | 1d | tradeify | 21 | $18,017 | $858 | 0.84 | 1.05 | $-3,827 | $15,018 | $-870 | $18,888 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 5m | tradeify | 171 | $2,257 | $13 | 0.84 | 1.38 | $-1,278 | $1,706 | $565 | $1,693 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 15m | tradeify | 155 | $5,142 | $33 | 0.79 | 1.37 | $-2,821 | $3,602 | $2,513 | $2,628 |
| 4.4 Mean-reversion (IBS) | MNQ | 1d | tradeify | 1509 | $11,627 | $8 | 0.78 | 1.06 | $-2,952 | $8,124 | $-6,944 | $18,571 |
| 3.1 Price momentum (12-1, time series) | MGC | 15m | tradeify | 54 | $2,848 | $53 | 0.77 | 1.36 | $-1,225 | $2,274 | $-692 | $3,540 |
| 3.17 Single-asset KNN | MNQ | 5m | tradeify | 701 | $4,363 | $6 | 0.76 | 1.32 | $-1,923 | $6,629 | $4,744 | $-381 |
| 3.11 Single moving average (EMA 50) | MGC | 1h | tradeify | 1326 | $10,671 | $8 | 0.72 | 1.09 | $-6,458 | $7,334 | $6,045 | $4,626 |
| 3.12 Two moving averages (10/30) | MNQ | 15m | tradeify | 175 | $5,398 | $31 | 0.71 | 1.33 | $-2,703 | $6,664 | $1,275 | $4,123 |
| 3.12 Two moving averages + 2% stop | MNQ | 15m | tradeify | 175 | $5,398 | $31 | 0.71 | 1.33 | $-2,703 | $6,664 | $1,275 | $4,123 |
| 8.1 Moving averages with HP filter | MES | 5m | tradeify | 143 | $1,646 | $12 | 0.71 | 1.32 | $-827 | $1,667 | $-544 | $2,190 |
| 3.9 Mean-reversion, single cluster | portfolio | 1d | tradeify | 4782 | $6,102 | $1 | 0.71 | 1.05 | $-1,559 | $9,750 | $-1,555 | $7,657 |
| 9.5 Skewness premium | portfolio | 15m | tradeify | 136 | $1,711 | $13 | 0.70 | 1.33 | $-728 | $2,740 | $151 | $1,560 |
| 3.11 Single moving average (SMA 50) | MNQ | 1h | tradeify | 1116 | $10,136 | $9 | 0.69 | 1.08 | $-2,758 | $15,690 | $5,691 | $4,445 |
| 8.1 Moving averages with HP filter | MGC | 1h | tradeify | 574 | $8,651 | $15 | 0.61 | 1.08 | $-3,435 | $13,183 | $-3,860 | $12,511 |
| 3.1 Price momentum (12-1, time series) | MGC | 1h | tradeify | 559 | $8,684 | $16 | 0.61 | 1.08 | $-3,345 | $10,880 | $-1,633 | $10,317 |
| 3.15 Channel, breakout (Donchian 20) | M2K | 15m | tradeify | 159 | $668 | $4 | 0.56 | 1.25 | $-413 | $1,058 | $-780 | $1,447 |
| 3.14 Support and resistance (pivot) | MGC | 15m | tradeify | 174 | $1,330 | $8 | 0.52 | 1.20 | $-705 | $3,332 | $1,033 | $298 |
| 10.4 Trend following (portfolio) | portfolio | 1h | tradeify | 2184 | $3,261 | $1 | 0.51 | 1.06 | $-1,373 | $6,329 | $-61 | $3,322 |
| 3.15 Channel, fade (Donchian 20) | MGC | 15m | tradeify | 192 | $2,217 | $12 | 0.49 | 1.19 | $-1,685 | $6,096 | $5,811 | $-3,594 |
| 8.1 Moving averages with HP filter | MGC | 5m | tradeify | 161 | $1,748 | $11 | 0.48 | 1.20 | $-1,097 | $2,753 | $-2,110 | $3,858 |
| 3.13 Three moving averages (3/10/21) | MNQ | 1h | tradeify | 1212 | $5,359 | $4 | 0.46 | 1.06 | $-1,933 | $12,856 | $2,432 | $2,927 |
| 4.4 Mean-reversion (IBS) | M2K | 1d | tradeify | 866 | $2,121 | $2 | 0.45 | 1.04 | $-766 | $4,932 | $-1,010 | $3,131 |
| 3.14 Support and resistance (pivot) | MGC | 5m | tradeify | 216 | $1,170 | $5 | 0.45 | 1.18 | $-1,059 | $2,369 | $1,073 | $97 |
| 9.6 Pricing model (OU mean-reversion) | MNQ | 1h | tradeify | 422 | $5,449 | $13 | 0.44 | 1.06 | $-4,193 | $7,375 | $-472 | $5,921 |
| 6.5 Volatility targeting (15%) | MGC | 1h | tradeify | 495 | $4,224 | $9 | 0.42 | 1.05 | $-1,428 | $15,675 | $12,659 | $-8,435 |
| 3.13 Three moving averages (3/10/21) | MGC | 15m | tradeify | 326 | $1,204 | $4 | 0.37 | 1.16 | $-594 | $4,914 | $-4,353 | $5,557 |
| 3.17 Single-asset KNN | MNQ | 1d | tradeify | 232 | $7,542 | $33 | 0.37 | 1.02 | $-2,498 | $16,984 | $-3,810 | $11,352 |
| 8.1 Moving averages with HP filter | MGC | 15m | tradeify | 72 | $1,531 | $21 | 0.36 | 1.15 | $-1,025 | $3,068 | $-256 | $1,787 |
| 3.13 Three moving averages (3/10/21) | MES | 15m | tradeify | 314 | $964 | $3 | 0.36 | 1.16 | $-783 | $2,618 | $-1,737 | $2,701 |
| 3.12 Two moving averages + 2% stop | MNQ | 1d | tradeify | 138 | $5,243 | $38 | 0.36 | 1.03 | $-2,780 | $11,519 | $-4,769 | $10,012 |
| 3.1 Price momentum (12-1, time series) | MGC | 5m | tradeify | 116 | $1,308 | $11 | 0.33 | 1.15 | $-1,002 | $3,466 | $-3,125 | $4,433 |
| 10.4 Trend following, one market | MNQ | 15m | tradeify | 56 | $2,163 | $39 | 0.32 | 1.13 | $-3,150 | $6,138 | $3,074 | $-911 |
| 10.4 Trend following, one market | MNQ | 5m | tradeify | 102 | $1,938 | $19 | 0.32 | 1.13 | $-2,863 | $4,536 | $477 | $1,461 |
| 8.1 Moving averages with HP filter | M2K | 5m | tradeify | 134 | $430 | $3 | 0.32 | 1.14 | $-467 | $1,242 | $-807 | $1,237 |
| 3.15 Channel, fade (Donchian 20) | MNQ | 1h | tradeify | 867 | $4,037 | $5 | 0.30 | 1.03 | $-2,430 | $13,481 | $6,328 | $-2,290 |
| 3.11 Single moving average (SMA 50) | MGC | 1h | tradeify | 1239 | $4,356 | $4 | 0.29 | 1.04 | $-6,458 | $13,885 | $5,127 | $-771 |
| 10.4 Trend following, one market | MGC | 5m | tradeify | 121 | $1,147 | $9 | 0.28 | 1.13 | $-1,208 | $4,360 | $-3,241 | $4,389 |
| 4.6 Multi-asset trend, w ~ R | portfolio | 1h | tradeify | 1026 | $2,518 | $2 | 0.26 | 1.04 | $-3,290 | $11,080 | $2,577 | $-59 |
| 9.5 Skewness premium | portfolio | 5m | tradeify | 271 | $529 | $2 | 0.25 | 1.10 | $-923 | $2,523 | $-642 | $1,171 |
| 4.6 Multi-asset trend, w ~ R/sigma | portfolio | 1h | tradeify | 1026 | $2,372 | $2 | 0.25 | 1.04 | $-3,248 | $10,996 | $2,741 | $-369 |
| 10.4 Trend following, one market | MGC | 1h | tradeify | 545 | $3,567 | $7 | 0.24 | 1.03 | $-3,345 | $14,308 | $-3,797 | $7,364 |
| 4.6 Multi-asset trend, w ~ R/sigma^2 | portfolio | 1h | tradeify | 1026 | $2,119 | $2 | 0.23 | 1.04 | $-3,174 | $10,874 | $2,949 | $-830 |
| 18.2 Neural network (MLP) | MGC | 15m | tradeify | 188 | $360 | $2 | 0.22 | 1.10 | $-600 | $1,469 | $878 | $-518 |
| 10.4 Trend following, one market | MNQ | 1d | tradeify | 13 | $4,428 | $341 | 0.21 | 1.01 | $-3,827 | $15,018 | $-2,485 | $6,913 |
| 9.3 Diversification with commodities (passive) | portfolio | 1h | tradeify | 986 | $1,851 | $2 | 0.21 | 1.03 | $-1,810 | $11,273 | $6,195 | $-4,344 |
| 18.2 Neural network (MLP) | MNQ | 15m | tradeify | 160 | $426 | $3 | 0.12 | 1.08 | $-1,551 | $2,876 | $-75 | $501 |
| 3.11 Single moving average (SMA 50) | MNQ | 5m | tradeify | 866 | $744 | $1 | 0.10 | 1.04 | $-4,082 | $5,298 | $-543 | $1,288 |
| 3.11 Single moving average (SMA 50) | MES | 15m | tradeify | 307 | $230 | $1 | 0.08 | 1.03 | $-828 | $3,217 | $-2,357 | $2,587 |
| 3.14 Support and resistance (pivot) | MGC | 1h | tradeify | 1417 | $644 | $0 | 0.06 | 1.01 | $-2,182 | $15,619 | $-4,533 | $5,177 |
| 18.2 Neural network (MLP) | M2K | 1h | tradeify | 485 | $36 | $0 | 0.04 | 1.01 | $-200 | $1,192 | $397 | $-360 |
| 3.4 Low-volatility anomaly | portfolio | 1h | tradeify | 1015 | $26 | $0 | 0.00 | 1.00 | $-1,608 | $7,400 | $656 | $-630 |

## Tier 1: every result with positive expectancy and positive net P&L (297)

### 1d (63)

| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6.5 Volatility targeting (15%) | MNQ | 1d | 24h | 1 | $47,577 | $47,577 | 2.74 | 1.16 | $-3,096 | $8,961 | $12,273 | $35,303 |
| 3.1 Price momentum (12-1, time series) | MNQ | 1d | 24h | 21 | $43,919 | $2,091 | 1.98 | 1.12 | $-3,630 | $12,714 | $9,355 | $34,564 |
| 18.2 Neural network (MLP) | MNQ | 1d | 24h | 365 | $42,288 | $116 | 2.38 | 1.18 | $-2,924 | $9,341 | $1,029 | $41,258 |
| 10.4 Trend following, one market | MNQ | 1d | 24h | 13 | $33,390 | $2,568 | 1.50 | 1.09 | $-3,630 | $12,714 | $7,759 | $25,631 |
| 6.5 Volatility targeting (15%) | MES | 1d | 24h | 1 | $30,766 | $30,766 | 2.40 | 1.13 | $-2,155 | $5,535 | $10,309 | $20,457 |
| 8.1 Moving averages with HP filter | MGC | 1d | 24h | 55 | $30,068 | $547 | 1.67 | 1.10 | $-5,733 | $11,985 | $-6,834 | $36,902 |
| 6.5 Volatility targeting (15%) | MGC | 1d | 24h | 1 | $28,365 | $28,365 | 1.96 | 1.10 | $-3,145 | $12,879 | $968 | $27,397 |
| 18.2 Neural network (MLP) | MNQ | 1d | tradeify | 365 | $27,426 | $75 | 1.61 | 1.12 | $-2,780 | $10,968 | $-2,048 | $29,473 |
| 4.4 Mean-reversion (IBS) | MNQ | 1d | 24h | 1509 | $26,864 | $18 | 1.69 | 1.14 | $-2,950 | $7,105 | $-4,888 | $31,751 |
| 4.1 Sector momentum rotation (long only) | portfolio | 1d | 24h | 39 | $26,270 | $674 | 1.41 | 1.11 | $-5,733 | $15,427 | $1,945 | $24,324 |
| 4.6 Multi-asset trend, w ~ R/sigma^2 | portfolio | 1d | 24h | 25 | $25,484 | $1,019 | 1.96 | 1.15 | $-3,280 | $7,138 | $560 | $24,924 |
| 4.6 Multi-asset trend, w ~ R/sigma | portfolio | 1d | 24h | 25 | $24,849 | $994 | 1.86 | 1.14 | $-3,258 | $7,847 | $569 | $24,280 |
| 9.3 Diversification with commodities (passive) | portfolio | 1d | 24h | 2 | $24,041 | $12,020 | 2.19 | 1.16 | $-2,934 | $9,159 | $1,150 | $22,891 |
| 4.6 Multi-asset trend, w ~ R | portfolio | 1d | 24h | 25 | $23,930 | $957 | 1.74 | 1.13 | $-3,220 | $8,675 | $580 | $23,350 |
| 3.11 Single moving average (SMA 50) | MGC | 1d | 24h | 290 | $21,420 | $74 | 1.19 | 1.07 | $-5,733 | $14,950 | $-2,971 | $24,391 |
| 3.17 Single-asset KNN | MNQ | 1d | 24h | 232 | $20,296 | $87 | 0.96 | 1.06 | $-3,363 | $10,974 | $3,355 | $16,942 |
| 3.1 Price momentum (12-1, time series) | MGC | 1d | 24h | 30 | $20,282 | $676 | 1.13 | 1.07 | $-5,733 | $14,439 | $1,675 | $18,606 |
| 3.11 Single moving average (EMA 50) | MNQ | 1d | 24h | 333 | $19,443 | $58 | 0.88 | 1.05 | $-4,090 | $13,645 | $-2,216 | $21,659 |
| 3.12 Two moving averages + 2% stop | MNQ | 1d | 24h | 138 | $18,792 | $136 | 1.26 | 1.10 | $-2,924 | $10,358 | $3,297 | $15,495 |
| 3.12 Two moving averages (10/30) | MGC | 1d | 24h | 165 | $18,520 | $112 | 1.02 | 1.06 | $-5,733 | $13,602 | $396 | $18,124 |
| 3.11 Single moving average (EMA 50) | MGC | 1d | 24h | 364 | $18,193 | $50 | 1.01 | 1.06 | $-5,733 | $14,264 | $618 | $17,575 |
| 3.1 Price momentum (12-1, time series) | MNQ | 1d | tradeify | 21 | $18,017 | $858 | 0.84 | 1.05 | $-3,827 | $15,018 | $-870 | $18,888 |
| 3.11 Single moving average (SMA 50) | MNQ | 1d | 24h | 272 | $17,977 | $66 | 0.81 | 1.05 | $-4,090 | $12,868 | $-1,015 | $18,992 |
| 6.5 Volatility targeting (15%) | MNQ | 1d | tradeify | 1 | $17,537 | $17,537 | 1.04 | 1.06 | $-2,947 | $9,128 | $-855 | $18,392 |
| 3.13 Three moving averages (3/10/21) | MGC | 1d | 24h | 325 | $17,430 | $54 | 1.13 | 1.08 | $-5,733 | $8,825 | $4,279 | $13,151 |
| 10.4 Trend following, one market | MES | 1d | 24h | 17 | $17,298 | $1,018 | 1.41 | 1.08 | $-1,688 | $7,354 | $2,836 | $14,461 |
| 10.4 Trend following (portfolio) | portfolio | 1d | 24h | 45 | $17,210 | $382 | 1.69 | 1.12 | $-1,696 | $5,408 | $320 | $16,890 |
| 10.4 Trend following, one market | MGC | 1d | 24h | 32 | $17,061 | $533 | 0.95 | 1.06 | $-5,733 | $14,439 | $-2,577 | $19,639 |
| 18.2 Neural network (MLP) | MES | 1d | 24h | 371 | $15,670 | $42 | 2.03 | 1.20 | $-1,398 | $3,615 | $-1,181 | $16,851 |
| 3.1 Price momentum (12-1, time series) | MES | 1d | 24h | 22 | $14,822 | $674 | 1.21 | 1.06 | $-1,688 | $6,769 | $3,258 | $11,565 |
| 3.12 Two moving averages (10/30) | MNQ | 1d | 24h | 145 | $14,801 | $102 | 0.67 | 1.04 | $-4,090 | $14,041 | $-28 | $14,829 |
| 4.1.2 Dual-momentum rotation | portfolio | 1d | 24h | 32 | $14,763 | $461 | 0.94 | 1.07 | $-3,630 | $9,601 | $1,421 | $13,342 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 1d | 24h | 32 | $12,803 | $400 | 0.77 | 1.06 | $-5,733 | $13,738 | $-2,394 | $15,197 |
| 4.4 Mean-reversion (IBS) | MNQ | 1d | tradeify | 1509 | $11,627 | $8 | 0.78 | 1.06 | $-2,952 | $8,124 | $-6,944 | $18,571 |
| 3.9 Mean-reversion, single cluster | portfolio | 1d | 24h | 4782 | $10,809 | $2 | 1.20 | 1.08 | $-1,617 | $7,523 | $-590 | $11,399 |
| 4.1.1 Rotation with MA filter | portfolio | 1d | 24h | 60 | $10,668 | $178 | 1.05 | 1.07 | $-2,866 | $7,125 | $780 | $9,888 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 1d | 24h | 133 | $9,463 | $71 | 0.42 | 1.02 | $-4,090 | $18,787 | $-3,333 | $12,797 |
| 3.15 Channel, breakout (Donchian 20) | MGC | 1d | 24h | 137 | $7,968 | $58 | 0.44 | 1.03 | $-5,733 | $13,682 | $888 | $7,079 |
| 18.2 Neural network (MLP) | MES | 1d | tradeify | 371 | $7,894 | $21 | 1.05 | 1.10 | $-943 | $6,360 | $-4,559 | $12,452 |
| 3.17 Single-asset KNN | MNQ | 1d | tradeify | 232 | $7,542 | $33 | 0.37 | 1.02 | $-2,498 | $16,984 | $-3,810 | $11,352 |
| 3.12 Two moving averages + 2% stop | MGC | 1d | 24h | 163 | $7,244 | $44 | 0.67 | 1.04 | $-2,091 | $9,334 | $2,027 | $5,216 |
| 3.17 Single-asset KNN | M2K | 1d | 24h | 131 | $7,010 | $54 | 1.14 | 1.08 | $-652 | $4,576 | $0 | $7,010 |
| 4.4 Mean-reversion (IBS) | MES | 1d | 24h | 1492 | $6,902 | $5 | 0.80 | 1.06 | $-1,568 | $6,868 | $-5,450 | $12,352 |
| 8.1 Moving averages with HP filter | MES | 1d | 24h | 36 | $6,532 | $181 | 0.53 | 1.03 | $-2,354 | $7,063 | $1,576 | $4,956 |
| 8.1 Moving averages with HP filter | MNQ | 1d | 24h | 52 | $6,467 | $124 | 0.29 | 1.02 | $-4,090 | $12,404 | $1,464 | $5,003 |
| 3.9 Mean-reversion, single cluster | portfolio | 1d | tradeify | 4782 | $6,102 | $1 | 0.71 | 1.05 | $-1,559 | $9,750 | $-1,555 | $7,657 |
| 4.1 Sector momentum rotation (long/short) | portfolio | 1d | 24h | 74 | $6,063 | $82 | 0.60 | 1.04 | $-2,799 | $8,892 | $886 | $5,177 |
| 3.4 Low-volatility anomaly | portfolio | 1d | 24h | 12 | $5,512 | $459 | 0.63 | 1.04 | $-1,392 | $7,108 | $-608 | $6,119 |
| 3.12 Two moving averages + 2% stop | MNQ | 1d | tradeify | 138 | $5,243 | $38 | 0.36 | 1.03 | $-2,780 | $11,519 | $-4,769 | $10,012 |
| 4.4 Mean-reversion (IBS) | M2K | 1d | 24h | 866 | $4,713 | $5 | 0.98 | 1.08 | $-764 | $4,162 | $-654 | $5,367 |
| 10.4 Trend following, one market | MNQ | 1d | tradeify | 13 | $4,428 | $341 | 0.21 | 1.01 | $-3,827 | $15,018 | $-2,485 | $6,913 |
| 3.17 Single-asset KNN | MES | 1d | 24h | 273 | $4,360 | $16 | 0.37 | 1.02 | $-2,354 | $8,085 | $636 | $3,724 |
| 3.14 Support and resistance (pivot) | MNQ | 1d | 24h | 1562 | $3,787 | $2 | 0.20 | 1.01 | $-4,090 | $15,087 | $-2,178 | $5,965 |
| 3.12 Two moving averages + 2% stop | MES | 1d | 24h | 134 | $3,357 | $25 | 0.38 | 1.02 | $-1,002 | $7,000 | $-471 | $3,828 |
| 3.17 Single-asset KNN | MGC | 1d | 24h | 214 | $3,000 | $14 | 0.20 | 1.01 | $-5,733 | $13,227 | $2,735 | $266 |
| 9.6 Pricing model (OU mean-reversion) | MES | 1d | 24h | 34 | $2,587 | $76 | 0.26 | 1.02 | $-1,399 | $9,490 | $401 | $2,187 |
| 6.5 Volatility targeting (15%) | M2K | 1d | 24h | 1 | $2,385 | $2,385 | 0.47 | 1.03 | $-631 | $3,760 | $2,123 | $262 |
| 4.4 Mean-reversion (IBS) | M2K | 1d | tradeify | 866 | $2,121 | $2 | 0.45 | 1.04 | $-766 | $4,932 | $-1,010 | $3,131 |
| 3.15 Channel, breakout (Donchian 20) | M2K | 1d | 24h | 67 | $1,550 | $23 | 0.23 | 1.01 | $-754 | $8,842 | $-5 | $1,555 |
| 3.15 Channel, breakout (Donchian 20) | MES | 1d | 24h | 135 | $1,467 | $11 | 0.12 | 1.01 | $-2,354 | $8,449 | $-4,450 | $5,917 |
| 3.12 Two moving averages + 2% stop | M2K | 1d | 24h | 93 | $692 | $7 | 0.15 | 1.01 | $-664 | $5,259 | $548 | $144 |
| 18.2 Neural network (MLP) | MGC | 1d | 24h | 218 | $326 | $2 | 0.07 | 1.01 | $-2,227 | $5,700 | $957 | $-631 |
| 3.12 Two moving averages (10/30) | MES | 1d | 24h | 137 | $294 | $2 | 0.02 | 1.00 | $-2,354 | $9,887 | $-3,044 | $3,338 |

### 1h (71)

| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.15 Channel, breakout (Donchian 20) | MGC | 1h | 24h | 345 | $28,277 | $82 | 2.08 | 1.28 | $-4,122 | $7,296 | $10,127 | $18,150 |
| 3.12 Two moving averages (10/30) | MGC | 1h | 24h | 421 | $27,087 | $64 | 2.00 | 1.26 | $-2,507 | $13,239 | $11,892 | $15,195 |
| 3.13 Three moving averages (3/10/21) | MGC | 1h | 24h | 892 | $26,088 | $29 | 2.18 | 1.31 | $-2,102 | $6,703 | $12,186 | $13,902 |
| 3.12 Two moving averages (10/30) | MGC | 1h | tradeify | 878 | $24,274 | $28 | 1.87 | 1.25 | $-2,298 | $11,497 | $8,898 | $15,376 |
| 3.12 Two moving averages + 2% stop | MGC | 1h | 24h | 421 | $24,135 | $57 | 1.80 | 1.23 | $-2,543 | $12,821 | $11,642 | $12,493 |
| 3.14 Support and resistance (pivot) | MNQ | 1h | 24h | 1140 | $22,980 | $20 | 1.94 | 1.25 | $-2,468 | $6,171 | $675 | $22,304 |
| 3.15 Channel, breakout (Donchian 20) | MGC | 1h | tradeify | 827 | $22,306 | $27 | 1.69 | 1.22 | $-4,258 | $6,339 | $6,587 | $15,719 |
| 3.13 Three moving averages (3/10/21) | MGC | 1h | tradeify | 1186 | $22,050 | $19 | 1.91 | 1.27 | $-2,230 | $6,618 | $9,649 | $12,401 |
| 3.14 Support and resistance (pivot) | MNQ | 1h | tradeify | 1293 | $21,873 | $17 | 1.92 | 1.25 | $-2,367 | $7,228 | $-178 | $22,050 |
| 3.12 Two moving averages + 2% stop | MGC | 1h | tradeify | 875 | $20,926 | $24 | 1.62 | 1.21 | $-2,679 | $11,164 | $8,602 | $12,324 |
| 3.1 Price momentum (12-1, time series) | MGC | 1h | 24h | 80 | $12,684 | $159 | 0.86 | 1.11 | $-3,467 | $10,697 | $1,909 | $10,774 |
| 9.5 Skewness premium | portfolio | 1h | 24h | 182 | $11,593 | $64 | 1.72 | 1.23 | $-1,224 | $4,329 | $7,859 | $3,733 |
| 6.5 Volatility targeting (15%) | MGC | 1h | 24h | 1 | $10,916 | $10,916 | 1.05 | 1.12 | $-1,444 | $15,907 | $17,260 | $-6,344 |
| 3.11 Single moving average (EMA 50) | MGC | 1h | tradeify | 1326 | $10,671 | $8 | 0.72 | 1.09 | $-6,458 | $7,334 | $6,045 | $4,626 |
| 10.4 Trend following, one market | MGC | 1h | 24h | 66 | $10,255 | $155 | 0.68 | 1.09 | $-3,467 | $13,751 | $494 | $9,761 |
| 3.11 Single moving average (SMA 50) | MNQ | 1h | tradeify | 1116 | $10,136 | $9 | 0.69 | 1.08 | $-2,758 | $15,690 | $5,691 | $4,445 |
| 3.11 Single moving average (EMA 50) | MGC | 1h | 24h | 891 | $9,770 | $11 | 0.63 | 1.08 | $-6,586 | $10,489 | $9,435 | $336 |
| 3.11 Single moving average (SMA 50) | MNQ | 1h | 24h | 675 | $9,379 | $14 | 0.61 | 1.07 | $-2,508 | $14,183 | $6,901 | $2,478 |
| 8.1 Moving averages with HP filter | MGC | 1h | 24h | 99 | $9,079 | $92 | 0.61 | 1.08 | $-3,467 | $13,242 | $-301 | $9,380 |
| 4.6 Multi-asset trend, w ~ R | portfolio | 1h | 24h | 154 | $8,761 | $57 | 0.88 | 1.14 | $-3,406 | $10,383 | $6,402 | $2,359 |
| 3.1 Price momentum (12-1, time series) | MGC | 1h | tradeify | 559 | $8,684 | $16 | 0.61 | 1.08 | $-3,345 | $10,880 | $-1,633 | $10,317 |
| 8.1 Moving averages with HP filter | MGC | 1h | tradeify | 574 | $8,651 | $15 | 0.61 | 1.08 | $-3,435 | $13,183 | $-3,860 | $12,511 |
| 4.6 Multi-asset trend, w ~ R/sigma | portfolio | 1h | 24h | 154 | $8,564 | $56 | 0.88 | 1.14 | $-3,362 | $10,342 | $6,681 | $1,883 |
| 4.6 Multi-asset trend, w ~ R/sigma^2 | portfolio | 1h | 24h | 154 | $8,265 | $54 | 0.87 | 1.14 | $-3,284 | $10,259 | $6,988 | $1,278 |
| 3.15 Channel, fade (Donchian 20) | MNQ | 1h | 24h | 399 | $7,972 | $20 | 0.56 | 1.06 | $-2,460 | $11,612 | $6,175 | $1,797 |
| 9.3 Diversification with commodities (passive) | portfolio | 1h | 24h | 2 | $7,842 | $3,921 | 0.85 | 1.11 | $-1,860 | $10,573 | $9,556 | $-1,713 |
| 3.11 Single moving average (SMA 50) | MGC | 1h | 24h | 811 | $6,566 | $8 | 0.42 | 1.05 | $-6,586 | $16,355 | $8,556 | $-1,989 |
| 3.13 Three moving averages (3/10/21) | MNQ | 1h | 24h | 902 | $6,399 | $7 | 0.52 | 1.06 | $-1,886 | $10,873 | $5,055 | $1,344 |
| 3.15 Channel, fade (Donchian 20) | M2K | 1h | 24h | 415 | $6,396 | $15 | 1.64 | 1.20 | $-500 | $2,208 | $1,178 | $5,217 |
| 9.5 Skewness premium | portfolio | 1h | tradeify | 1135 | $6,316 | $6 | 0.97 | 1.12 | $-1,308 | $4,739 | $5,603 | $713 |
| 9.6 Pricing model (OU mean-reversion) | MNQ | 1h | tradeify | 422 | $5,449 | $13 | 0.44 | 1.06 | $-4,193 | $7,375 | $-472 | $5,921 |
| 3.13 Three moving averages (3/10/21) | MNQ | 1h | tradeify | 1212 | $5,359 | $4 | 0.46 | 1.06 | $-1,933 | $12,856 | $2,432 | $2,927 |
| 3.15 Channel, fade (Donchian 20) | M2K | 1h | tradeify | 886 | $5,167 | $6 | 1.40 | 1.17 | $-432 | $2,823 | $152 | $5,015 |
| 3.1 Price momentum (12-1, time series) | MNQ | 1h | rth | 504 | $5,115 | $10 | 0.55 | 1.07 | $-2,665 | $7,809 | $-75 | $5,190 |
| 10.4 Trend following (portfolio) | portfolio | 1h | 24h | 285 | $5,022 | $18 | 0.74 | 1.09 | $-1,432 | $3,747 | $832 | $4,190 |
| 4.1 Sector momentum rotation (long only) | portfolio | 1h | 24h | 146 | $4,939 | $34 | 0.37 | 1.05 | $-3,467 | $12,666 | $4,422 | $518 |
| 3.4 Low-volatility anomaly | portfolio | 1h | 24h | 54 | $4,710 | $87 | 0.68 | 1.09 | $-1,764 | $8,021 | $4,850 | $-140 |
| 3.11 Single moving average (SMA 50) | MGC | 1h | tradeify | 1239 | $4,356 | $4 | 0.29 | 1.04 | $-6,458 | $13,885 | $5,127 | $-771 |
| 3.13 Three moving averages (3/10/21) | MNQ | 1h | rth | 529 | $4,265 | $8 | 0.51 | 1.07 | $-2,043 | $4,330 | $1,735 | $2,530 |
| 6.5 Volatility targeting (15%) | MGC | 1h | tradeify | 495 | $4,224 | $9 | 0.42 | 1.05 | $-1,428 | $15,675 | $12,659 | $-8,435 |
| 3.15 Channel, fade (Donchian 20) | MNQ | 1h | tradeify | 867 | $4,037 | $5 | 0.30 | 1.03 | $-2,430 | $13,481 | $6,328 | $-2,290 |
| 6.5 Volatility targeting (15%) | MNQ | 1h | 24h | 1 | $3,996 | $3,996 | 0.30 | 1.03 | $-2,316 | $13,995 | $7,659 | $-3,664 |
| 9.6 Pricing model (OU mean-reversion) | MNQ | 1h | rth | 360 | $3,994 | $11 | 0.50 | 1.09 | $-3,098 | $5,928 | $2,400 | $1,594 |
| 3.13 Three moving averages (3/10/21) | MGC | 1h | rth | 493 | $3,889 | $8 | 0.63 | 1.10 | $-795 | $6,627 | $3,662 | $227 |
| 4.1.2 Dual-momentum rotation | portfolio | 1h | 24h | 164 | $3,807 | $23 | 0.31 | 1.04 | $-2,289 | $11,289 | $6,259 | $-2,452 |
| 3.14 Support and resistance (pivot) | MNQ | 1h | rth | 472 | $3,594 | $8 | 0.53 | 1.08 | $-1,763 | $6,909 | $-3,316 | $6,910 |
| 10.4 Trend following, one market | MGC | 1h | tradeify | 545 | $3,567 | $7 | 0.24 | 1.03 | $-3,345 | $14,308 | $-3,797 | $7,364 |
| 10.4 Trend following (portfolio) | portfolio | 1h | tradeify | 2184 | $3,261 | $1 | 0.51 | 1.06 | $-1,373 | $6,329 | $-61 | $3,322 |
| 3.4 Low-volatility anomaly | portfolio | 1h | rth | 987 | $3,211 | $3 | 0.87 | 1.14 | $-533 | $1,999 | $-1,297 | $4,507 |
| 9.6 Pricing model (OU mean-reversion) | MNQ | 1h | 24h | 122 | $3,125 | $26 | 0.24 | 1.03 | $-4,180 | $7,951 | $-717 | $3,842 |
| 3.1 Price momentum (12-1, time series) | MES | 1h | rth | 509 | $2,955 | $6 | 0.60 | 1.08 | $-1,588 | $3,659 | $1,109 | $1,845 |
| 3.11 Single moving average (SMA 50) | MNQ | 1h | rth | 656 | $2,915 | $4 | 0.31 | 1.04 | $-1,896 | $9,512 | $-111 | $3,026 |
| 4.6 Multi-asset trend, w ~ R | portfolio | 1h | tradeify | 1026 | $2,518 | $2 | 0.26 | 1.04 | $-3,290 | $11,080 | $2,577 | $-59 |
| 4.6 Multi-asset trend, w ~ R/sigma | portfolio | 1h | tradeify | 1026 | $2,372 | $2 | 0.25 | 1.04 | $-3,248 | $10,996 | $2,741 | $-369 |
| 3.12 Two moving averages (10/30) | MGC | 1h | rth | 592 | $2,316 | $4 | 0.33 | 1.05 | $-1,243 | $6,218 | $667 | $1,649 |
| 4.6 Multi-asset trend, w ~ R/sigma^2 | portfolio | 1h | tradeify | 1026 | $2,119 | $2 | 0.23 | 1.04 | $-3,174 | $10,874 | $2,949 | $-830 |
| 9.5 Skewness premium | portfolio | 1h | rth | 1003 | $2,069 | $2 | 0.54 | 1.08 | $-1,886 | $2,448 | $2,974 | $-905 |
| 9.3 Diversification with commodities (passive) | portfolio | 1h | tradeify | 986 | $1,851 | $2 | 0.21 | 1.03 | $-1,810 | $11,273 | $6,195 | $-4,344 |
| 3.14 Support and resistance (pivot) | MGC | 1h | 24h | 1246 | $1,565 | $1 | 0.14 | 1.02 | $-2,116 | $14,949 | $-3,757 | $5,322 |
| 3.1 Price momentum (12-1, time series) | M2K | 1h | 24h | 71 | $1,316 | $19 | 0.34 | 1.04 | $-938 | $2,466 | $957 | $359 |
| 3.15 Channel, fade (Donchian 20) | MES | 1h | 24h | 389 | $1,151 | $3 | 0.17 | 1.02 | $-1,521 | $4,514 | $907 | $243 |
| 6.5 Volatility targeting (15%) | MES | 1h | 24h | 1 | $1,059 | $1,059 | 0.13 | 1.01 | $-1,583 | $6,201 | $2,817 | $-1,759 |
| 10.4 Trend following, one market | MNQ | 1h | rth | 503 | $934 | $2 | 0.10 | 1.01 | $-2,665 | $11,415 | $-1,411 | $2,345 |
| 3.11 Single moving average (EMA 50) | MNQ | 1h | rth | 689 | $767 | $1 | 0.08 | 1.01 | $-1,606 | $9,598 | $-872 | $1,640 |
| 3.14 Support and resistance (pivot) | MGC | 1h | tradeify | 1417 | $644 | $0 | 0.06 | 1.01 | $-2,182 | $15,619 | $-4,533 | $5,177 |
| 18.2 Neural network (MLP) | M2K | 1h | 24h | 480 | $532 | $1 | 0.48 | 1.09 | $-200 | $1,279 | $931 | $-400 |
| 3.15 Channel, fade (Donchian 20) | M2K | 1h | rth | 622 | $383 | $1 | 0.15 | 1.02 | $-400 | $2,420 | $948 | $-565 |
| 18.2 Neural network (MLP) | M2K | 1h | rth | 226 | $353 | $2 | 0.43 | 1.09 | $-182 | $723 | $593 | $-240 |
| 18.2 Neural network (MLP) | MNQ | 1h | 24h | 298 | $223 | $1 | 0.06 | 1.01 | $-1,464 | $4,684 | $-454 | $677 |
| 18.2 Neural network (MLP) | M2K | 1h | tradeify | 485 | $36 | $0 | 0.04 | 1.01 | $-200 | $1,192 | $397 | $-360 |
| 3.4 Low-volatility anomaly | portfolio | 1h | tradeify | 1015 | $26 | $0 | 0.00 | 1.00 | $-1,608 | $7,400 | $656 | $-630 |

### 15m (92)

| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.11 Single moving average (EMA 50) | MNQ | 15m | rth | 118 | $9,282 | $79 | 1.84 | 2.20 | $-1,020 | $1,398 | $1,102 | $8,180 |
| 3.11 Single moving average (SMA 50) | MNQ | 15m | rth | 105 | $8,440 | $80 | 1.81 | 2.23 | $-949 | $1,476 | $1,015 | $7,424 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 15m | rth | 74 | $8,178 | $111 | 1.79 | 2.43 | $-1,607 | $2,385 | $1,669 | $6,509 |
| 3.11 Single moving average (EMA 50) | MNQ | 15m | tradeify | 342 | $7,153 | $21 | 1.12 | 1.54 | $-1,804 | $3,252 | $-1,285 | $8,438 |
| 3.13 Three moving averages (3/10/21) | MNQ | 15m | 24h | 293 | $6,927 | $24 | 1.26 | 1.66 | $-1,615 | $4,022 | $-976 | $7,903 |
| 3.11 Single moving average (EMA 50) | MNQ | 15m | 24h | 306 | $6,730 | $22 | 1.03 | 1.49 | $-1,844 | $3,219 | $-585 | $7,315 |
| 3.13 Three moving averages (3/10/21) | MNQ | 15m | tradeify | 316 | $6,396 | $20 | 1.14 | 1.60 | $-1,615 | $4,062 | $-875 | $7,271 |
| 3.13 Three moving averages (3/10/21) | MNQ | 15m | rth | 99 | $5,564 | $56 | 1.18 | 1.72 | $-1,144 | $1,728 | $487 | $5,077 |
| 3.12 Two moving averages (10/30) | MNQ | 15m | tradeify | 175 | $5,398 | $31 | 0.71 | 1.33 | $-2,703 | $6,664 | $1,275 | $4,123 |
| 3.12 Two moving averages + 2% stop | MNQ | 15m | tradeify | 175 | $5,398 | $31 | 0.71 | 1.33 | $-2,703 | $6,664 | $1,275 | $4,123 |
| 3.12 Two moving averages + 2% stop | MNQ | 15m | rth | 69 | $5,397 | $78 | 0.91 | 1.52 | $-1,584 | $3,326 | $316 | $5,081 |
| 3.12 Two moving averages (10/30) | MNQ | 15m | rth | 69 | $5,397 | $78 | 0.91 | 1.52 | $-1,584 | $3,326 | $316 | $5,081 |
| 3.11 Single moving average (SMA 50) | MNQ | 15m | tradeify | 309 | $5,339 | $17 | 0.86 | 1.40 | $-2,682 | $4,064 | $-1,551 | $6,890 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 15m | tradeify | 155 | $5,142 | $33 | 0.79 | 1.37 | $-2,821 | $3,602 | $2,513 | $2,628 |
| 3.15 Channel, breakout (Donchian 20) | MES | 15m | rth | 69 | $4,742 | $69 | 2.16 | 3.14 | $-405 | $807 | $292 | $4,451 |
| 3.12 Two moving averages + 2% stop | MNQ | 15m | 24h | 135 | $4,636 | $34 | 0.59 | 1.26 | $-2,914 | $6,480 | $518 | $4,118 |
| 3.12 Two moving averages (10/30) | MNQ | 15m | 24h | 135 | $4,636 | $34 | 0.59 | 1.26 | $-2,914 | $6,480 | $518 | $4,118 |
| 3.11 Single moving average (SMA 50) | MES | 15m | rth | 103 | $4,632 | $45 | 1.94 | 2.64 | $-457 | $718 | $-55 | $4,687 |
| 3.11 Single moving average (SMA 50) | MNQ | 15m | 24h | 275 | $4,303 | $16 | 0.69 | 1.29 | $-2,239 | $4,607 | $-1,458 | $5,761 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 15m | 24h | 115 | $4,267 | $37 | 0.66 | 1.28 | $-2,589 | $3,451 | $2,039 | $2,228 |
| 10.4 Trend following, one market | MGC | 15m | tradeify | 52 | $4,130 | $79 | 0.99 | 1.52 | $-1,996 | $1,996 | $-188 | $4,318 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 15m | rth | 38 | $4,071 | $107 | 2.44 | 3.44 | $-421 | $915 | $-776 | $4,848 |
| 8.1 Moving averages with HP filter | MNQ | 15m | rth | 50 | $3,879 | $78 | 0.78 | 1.41 | $-1,629 | $1,805 | $1,685 | $2,194 |
| 3.15 Channel, fade (Donchian 20) | MGC | 15m | 24h | 153 | $3,623 | $24 | 0.83 | 1.35 | $-1,624 | $5,075 | $6,297 | $-2,674 |
| 4.1 Sector momentum rotation (long/short) | portfolio | 15m | tradeify | 178 | $3,431 | $19 | 1.47 | 1.76 | $-1,040 | $1,729 | $740 | $2,691 |
| 4.1.1 Rotation with MA filter | portfolio | 15m | rth | 87 | $3,202 | $37 | 1.31 | 1.89 | $-889 | $889 | $773 | $2,429 |
| 10.4 Trend following (portfolio) | portfolio | 15m | rth | 184 | $3,192 | $17 | 1.92 | 2.40 | $-474 | $698 | $979 | $2,213 |
| 3.13 Three moving averages (3/10/21) | MES | 15m | rth | 95 | $3,178 | $33 | 1.42 | 1.97 | $-412 | $1,000 | $92 | $3,086 |
| 4.1 Sector momentum rotation (long/short) | portfolio | 15m | rth | 110 | $3,113 | $28 | 1.33 | 1.86 | $-888 | $957 | $955 | $2,159 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 15m | tradeify | 58 | $3,098 | $53 | 1.11 | 1.67 | $-974 | $1,696 | $-1,420 | $4,518 |
| 4.1 Sector momentum rotation (long/short) | portfolio | 15m | 24h | 98 | $3,094 | $32 | 1.28 | 1.62 | $-932 | $1,957 | $683 | $2,411 |
| 3.11 Single moving average (EMA 50) | MES | 15m | rth | 127 | $3,075 | $24 | 1.24 | 1.79 | $-753 | $1,175 | $-660 | $3,735 |
| 3.15 Channel, breakout (Donchian 20) | MES | 15m | 24h | 119 | $2,989 | $25 | 1.09 | 1.61 | $-678 | $1,638 | $-904 | $3,893 |
| 3.1 Price momentum (12-1, time series) | MGC | 15m | rth | 43 | $2,876 | $67 | 1.32 | 1.74 | $-1,015 | $1,099 | $-729 | $3,605 |
| 10.4 Trend following, one market | MGC | 15m | 24h | 15 | $2,856 | $190 | 0.67 | 1.32 | $-2,131 | $2,467 | $-553 | $3,409 |
| 3.4 Low-volatility anomaly | portfolio | 15m | rth | 82 | $2,851 | $35 | 1.55 | 2.16 | $-469 | $821 | $-98 | $2,948 |
| 3.1 Price momentum (12-1, time series) | MGC | 15m | tradeify | 54 | $2,848 | $53 | 0.77 | 1.36 | $-1,225 | $2,274 | $-692 | $3,540 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 15m | 24h | 28 | $2,845 | $102 | 0.99 | 1.56 | $-960 | $1,580 | $-1,127 | $3,972 |
| 10.4 Trend following (portfolio) | portfolio | 15m | tradeify | 230 | $2,703 | $12 | 1.23 | 1.63 | $-664 | $1,167 | $756 | $1,947 |
| 10.4 Trend following, one market | MGC | 15m | rth | 44 | $2,693 | $61 | 1.14 | 1.67 | $-1,398 | $1,708 | $-1,314 | $4,007 |
| 3.15 Channel, breakout (Donchian 20) | MES | 15m | tradeify | 159 | $2,661 | $17 | 0.97 | 1.50 | $-463 | $1,647 | $-1,037 | $3,698 |
| 3.4 Low-volatility anomaly | portfolio | 15m | tradeify | 96 | $2,607 | $27 | 1.20 | 1.61 | $-754 | $1,242 | $372 | $2,234 |
| 10.4 Trend following, one market | MES | 15m | rth | 43 | $2,590 | $60 | 1.01 | 1.63 | $-1,226 | $2,497 | $867 | $1,724 |
| 4.1.1 Rotation with MA filter | portfolio | 15m | tradeify | 143 | $2,485 | $17 | 1.06 | 1.50 | $-1,058 | $2,224 | $581 | $1,904 |
| 3.1 Price momentum (12-1, time series) | MES | 15m | rth | 44 | $2,325 | $53 | 0.84 | 1.53 | $-1,576 | $2,622 | $77 | $2,247 |
| 3.15 Channel, fade (Donchian 20) | MGC | 15m | tradeify | 192 | $2,217 | $12 | 0.49 | 1.19 | $-1,685 | $6,096 | $5,811 | $-3,594 |
| 10.4 Trend following, one market | MNQ | 15m | tradeify | 56 | $2,163 | $39 | 0.32 | 1.13 | $-3,150 | $6,138 | $3,074 | $-911 |
| 10.4 Trend following, one market | MNQ | 15m | rth | 45 | $2,112 | $47 | 0.40 | 1.19 | $-2,277 | $4,867 | $3,420 | $-1,309 |
| 8.1 Moving averages with HP filter | MGC | 15m | rth | 44 | $1,985 | $45 | 0.91 | 1.47 | $-1,015 | $2,069 | $1,138 | $847 |
| 9.5 Skewness premium | portfolio | 15m | 24h | 58 | $1,979 | $34 | 0.81 | 1.38 | $-777 | $2,724 | $437 | $1,542 |
| 3.4 Low-volatility anomaly | portfolio | 15m | 24h | 18 | $1,942 | $108 | 0.84 | 1.41 | $-854 | $1,460 | $375 | $1,567 |
| 4.1.1 Rotation with MA filter | portfolio | 15m | 24h | 81 | $1,905 | $24 | 0.77 | 1.34 | $-945 | $2,501 | $506 | $1,399 |
| 3.1 Price momentum (12-1, time series) | MGC | 15m | 24h | 16 | $1,803 | $113 | 0.47 | 1.20 | $-1,270 | $2,706 | $-863 | $2,666 |
| 3.12 Two moving averages + 2% stop | MES | 15m | rth | 74 | $1,734 | $23 | 0.68 | 1.34 | $-659 | $1,205 | $-622 | $2,356 |
| 3.12 Two moving averages (10/30) | MES | 15m | rth | 74 | $1,734 | $23 | 0.68 | 1.34 | $-659 | $1,205 | $-622 | $2,356 |
| 9.5 Skewness premium | portfolio | 15m | tradeify | 136 | $1,711 | $13 | 0.70 | 1.33 | $-728 | $2,740 | $151 | $1,560 |
| 10.4 Trend following (portfolio) | portfolio | 15m | 24h | 77 | $1,678 | $22 | 0.71 | 1.33 | $-766 | $1,492 | $558 | $1,120 |
| 8.1 Moving averages with HP filter | MGC | 15m | tradeify | 72 | $1,531 | $21 | 0.36 | 1.15 | $-1,025 | $3,068 | $-256 | $1,787 |
| 3.15 Channel, fade (Donchian 20) | MGC | 15m | rth | 78 | $1,347 | $17 | 0.57 | 1.24 | $-745 | $1,884 | $2,053 | $-706 |
| 3.14 Support and resistance (pivot) | MGC | 15m | tradeify | 174 | $1,330 | $8 | 0.52 | 1.20 | $-705 | $3,332 | $1,033 | $298 |
| 8.1 Moving averages with HP filter | MES | 15m | rth | 50 | $1,246 | $25 | 0.52 | 1.29 | $-1,086 | $1,208 | $-248 | $1,494 |
| 3.13 Three moving averages (3/10/21) | MGC | 15m | tradeify | 326 | $1,204 | $4 | 0.37 | 1.16 | $-594 | $4,914 | $-4,353 | $5,557 |
| 3.11 Single moving average (EMA 50) | MGC | 15m | rth | 106 | $1,190 | $11 | 0.53 | 1.23 | $-606 | $1,262 | $58 | $1,132 |
| 9.6 Pricing model (OU mean-reversion) | MNQ | 15m | rth | 35 | $1,132 | $32 | 0.31 | 1.16 | $-878 | $2,755 | $-2,388 | $3,519 |
| 3.13 Three moving averages (3/10/21) | MES | 15m | 24h | 300 | $1,052 | $4 | 0.39 | 1.18 | $-783 | $2,662 | $-1,753 | $2,804 |
| 3.14 Support and resistance (pivot) | MGC | 15m | 24h | 156 | $1,018 | $7 | 0.38 | 1.14 | $-726 | $3,330 | $1,070 | $-52 |
| 3.13 Three moving averages (3/10/21) | MGC | 15m | 24h | 312 | $981 | $3 | 0.30 | 1.12 | $-594 | $4,892 | $-4,326 | $5,307 |
| 3.13 Three moving averages (3/10/21) | MES | 15m | tradeify | 314 | $964 | $3 | 0.36 | 1.16 | $-783 | $2,618 | $-1,737 | $2,701 |
| 9.5 Skewness premium | portfolio | 15m | rth | 97 | $941 | $10 | 0.59 | 1.31 | $-556 | $1,167 | $397 | $543 |
| 18.2 Neural network (MLP) | MGC | 15m | rth | 68 | $925 | $14 | 0.51 | 1.37 | $-1,306 | $1,306 | $496 | $429 |
| 3.13 Three moving averages (3/10/21) | M2K | 15m | rth | 99 | $901 | $9 | 0.94 | 1.51 | $-264 | $368 | $-37 | $938 |
| 3.15 Channel, breakout (Donchian 20) | M2K | 15m | 24h | 117 | $848 | $7 | 0.71 | 1.32 | $-416 | $1,018 | $-716 | $1,564 |
| 3.11 Single moving average (SMA 50) | MGC | 15m | rth | 109 | $847 | $8 | 0.40 | 1.17 | $-675 | $1,742 | $-669 | $1,516 |
| 3.15 Channel, breakout (Donchian 20) | M2K | 15m | rth | 76 | $726 | $10 | 0.72 | 1.39 | $-262 | $726 | $-204 | $931 |
| 3.15 Channel, breakout (Donchian 20) | M2K | 15m | tradeify | 159 | $668 | $4 | 0.56 | 1.25 | $-413 | $1,058 | $-780 | $1,447 |
| 3.11 Single moving average (EMA 50) | M2K | 15m | rth | 113 | $630 | $6 | 0.56 | 1.27 | $-316 | $719 | $-240 | $870 |
| 3.13 Three moving averages (3/10/21) | MGC | 15m | rth | 105 | $622 | $6 | 0.32 | 1.14 | $-523 | $1,552 | $-1,215 | $1,837 |
| 3.1 Price momentum (12-1, time series) | MNQ | 15m | rth | 42 | $600 | $14 | 0.10 | 1.05 | $-2,712 | $5,311 | $3,315 | $-2,715 |
| 3.12 Two moving averages (10/30) | M2K | 15m | rth | 78 | $557 | $7 | 0.50 | 1.24 | $-263 | $729 | $-282 | $840 |
| 3.12 Two moving averages + 2% stop | M2K | 15m | rth | 78 | $557 | $7 | 0.50 | 1.24 | $-263 | $729 | $-282 | $840 |
| 8.1 Moving averages with HP filter | MGC | 15m | 24h | 34 | $550 | $16 | 0.13 | 1.05 | $-1,011 | $3,022 | $-426 | $976 |
| 9.6 Pricing model (OU mean-reversion) | MES | 15m | rth | 41 | $535 | $13 | 0.28 | 1.17 | $-608 | $1,340 | $-459 | $994 |
| 3.11 Single moving average (SMA 50) | M2K | 15m | rth | 109 | $501 | $5 | 0.45 | 1.21 | $-252 | $815 | $-342 | $843 |
| 18.2 Neural network (MLP) | MNQ | 15m | tradeify | 160 | $426 | $3 | 0.12 | 1.08 | $-1,551 | $2,876 | $-75 | $501 |
| 18.2 Neural network (MLP) | MGC | 15m | tradeify | 188 | $360 | $2 | 0.22 | 1.10 | $-600 | $1,469 | $878 | $-518 |
| 18.2 Neural network (MLP) | MNQ | 15m | 24h | 160 | $255 | $2 | 0.07 | 1.04 | $-1,551 | $2,876 | $-328 | $583 |
| 3.11 Single moving average (SMA 50) | MES | 15m | tradeify | 307 | $230 | $1 | 0.08 | 1.03 | $-828 | $3,217 | $-2,357 | $2,587 |
| 3.17 Single-asset KNN | M2K | 15m | rth | 118 | $213 | $2 | 0.25 | 1.13 | $-242 | $580 | $-417 | $629 |
| 3.14 Support and resistance (pivot) | MNQ | 15m | 24h | 170 | $201 | $1 | 0.04 | 1.02 | $-2,817 | $5,472 | $-2,898 | $3,098 |
| 3.12 Two moving averages (10/30) | M2K | 15m | 24h | 155 | $144 | $1 | 0.11 | 1.04 | $-554 | $1,097 | $-489 | $633 |
| 3.12 Two moving averages + 2% stop | M2K | 15m | 24h | 155 | $144 | $1 | 0.11 | 1.04 | $-554 | $1,097 | $-489 | $633 |
| 3.1 Price momentum (12-1, time series) | M2K | 15m | rth | 44 | $61 | $1 | 0.05 | 1.03 | $-652 | $1,459 | $-232 | $292 |

### 5m (71)

| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8.1 Moving averages with HP filter | MNQ | 5m | tradeify | 131 | $10,999 | $84 | 1.83 | 2.02 | $-3,080 | $3,630 | $1,983 | $9,017 |
| 8.1 Moving averages with HP filter | MNQ | 5m | 24h | 92 | $9,243 | $100 | 1.39 | 1.71 | $-3,612 | $4,810 | $1,731 | $7,512 |
| 3.12 Two moving averages (10/30) | MNQ | 5m | 24h | 435 | $7,344 | $17 | 1.22 | 1.51 | $-1,418 | $4,231 | $-506 | $7,850 |
| 3.12 Two moving averages + 2% stop | MNQ | 5m | 24h | 435 | $7,344 | $17 | 1.22 | 1.51 | $-1,418 | $4,231 | $-506 | $7,850 |
| 3.11 Single moving average (SMA 50) | MNQ | 5m | rth | 249 | $6,958 | $28 | 1.42 | 1.83 | $-1,722 | $2,478 | $2,682 | $4,276 |
| 3.12 Two moving averages + 2% stop | MNQ | 5m | tradeify | 477 | $5,757 | $12 | 1.00 | 1.42 | $-1,434 | $4,644 | $-1,534 | $7,291 |
| 3.12 Two moving averages (10/30) | MNQ | 5m | tradeify | 477 | $5,757 | $12 | 1.00 | 1.42 | $-1,434 | $4,644 | $-1,534 | $7,291 |
| 10.4 Trend following, one market | MNQ | 5m | rth | 59 | $5,463 | $93 | 1.11 | 1.63 | $-1,303 | $1,884 | $-151 | $5,613 |
| 8.1 Moving averages with HP filter | MNQ | 5m | rth | 65 | $4,699 | $72 | 1.22 | 1.66 | $-934 | $3,103 | $3,259 | $1,440 |
| 3.17 Single-asset KNN | MNQ | 5m | rth | 255 | $4,454 | $17 | 0.96 | 1.50 | $-1,306 | $3,789 | $3,374 | $1,081 |
| 3.17 Single-asset KNN | MNQ | 5m | tradeify | 701 | $4,363 | $6 | 0.76 | 1.32 | $-1,923 | $6,629 | $4,744 | $-381 |
| 3.11 Single moving average (EMA 50) | MNQ | 5m | rth | 285 | $4,230 | $15 | 0.81 | 1.41 | $-1,802 | $2,117 | $962 | $3,268 |
| 3.15 Channel, breakout (Donchian 20) | MES | 5m | rth | 129 | $4,146 | $32 | 1.78 | 2.22 | $-934 | $1,561 | $702 | $3,445 |
| 3.17 Single-asset KNN | MNQ | 5m | 24h | 667 | $3,465 | $5 | 0.56 | 1.22 | $-1,966 | $6,885 | $4,451 | $-986 |
| 3.15 Channel, breakout (Donchian 20) | MES | 5m | 24h | 345 | $3,246 | $9 | 1.12 | 1.56 | $-1,243 | $2,217 | $-870 | $4,116 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 5m | 24h | 140 | $2,720 | $19 | 0.99 | 1.46 | $-1,278 | $1,716 | $758 | $1,961 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 5m | rth | 148 | $2,584 | $17 | 0.57 | 1.27 | $-1,691 | $3,336 | $127 | $2,458 |
| 3.12 Two moving averages + 2% stop | MES | 5m | rth | 147 | $2,533 | $17 | 1.12 | 1.59 | $-557 | $1,702 | $-368 | $2,901 |
| 3.12 Two moving averages (10/30) | MES | 5m | rth | 148 | $2,514 | $17 | 1.11 | 1.59 | $-557 | $1,722 | $-387 | $2,901 |
| 3.15 Channel, breakout (Donchian 20) | MES | 5m | tradeify | 384 | $2,459 | $6 | 0.86 | 1.43 | $-1,267 | $2,455 | $-1,248 | $3,707 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 5m | tradeify | 171 | $2,257 | $13 | 0.84 | 1.38 | $-1,278 | $1,706 | $565 | $1,693 |
| 3.12 Two moving averages (10/30) | MNQ | 5m | rth | 166 | $2,255 | $14 | 0.50 | 1.24 | $-1,336 | $1,707 | $299 | $1,957 |
| 3.12 Two moving averages + 2% stop | MNQ | 5m | rth | 166 | $2,255 | $14 | 0.50 | 1.24 | $-1,336 | $1,707 | $299 | $1,957 |
| 3.4 Low-volatility anomaly | portfolio | 5m | tradeify | 136 | $2,128 | $16 | 1.05 | 1.52 | $-789 | $1,069 | $826 | $1,302 |
| 4.1.1 Rotation with MA filter | portfolio | 5m | tradeify | 318 | $1,980 | $6 | 0.92 | 1.38 | $-584 | $1,947 | $-2,006 | $3,986 |
| 10.4 Trend following, one market | MNQ | 5m | tradeify | 102 | $1,938 | $19 | 0.32 | 1.13 | $-2,863 | $4,536 | $477 | $1,461 |
| 3.11 Single moving average (SMA 50) | MES | 5m | rth | 256 | $1,755 | $7 | 0.59 | 1.31 | $-1,553 | $2,340 | $-624 | $2,380 |
| 8.1 Moving averages with HP filter | MGC | 5m | tradeify | 161 | $1,748 | $11 | 0.48 | 1.20 | $-1,097 | $2,753 | $-2,110 | $3,858 |
| 3.4 Low-volatility anomaly | portfolio | 5m | rth | 97 | $1,720 | $18 | 1.14 | 1.68 | $-512 | $766 | $282 | $1,438 |
| 3.12 Two moving averages + 2% stop | M2K | 5m | rth | 144 | $1,703 | $12 | 1.82 | 2.11 | $-345 | $398 | $339 | $1,364 |
| 3.12 Two moving averages (10/30) | M2K | 5m | rth | 144 | $1,703 | $12 | 1.82 | 2.11 | $-345 | $398 | $339 | $1,364 |
| 8.1 Moving averages with HP filter | MES | 5m | tradeify | 143 | $1,646 | $12 | 0.71 | 1.32 | $-827 | $1,667 | $-544 | $2,190 |
| 9.6 Pricing model (OU mean-reversion) | MGC | 5m | rth | 78 | $1,555 | $20 | 0.86 | 1.43 | $-732 | $1,506 | $349 | $1,206 |
| 3.4 Low-volatility anomaly | portfolio | 5m | 24h | 54 | $1,507 | $28 | 0.70 | 1.31 | $-854 | $1,460 | $869 | $638 |
| 3.11 Single moving average (EMA 50) | MES | 5m | rth | 270 | $1,469 | $5 | 0.52 | 1.27 | $-997 | $2,414 | $-1,211 | $2,680 |
| 4.1.1 Rotation with MA filter | portfolio | 5m | rth | 143 | $1,467 | $10 | 0.79 | 1.44 | $-330 | $1,273 | $-545 | $2,012 |
| 3.15 Channel, breakout (Donchian 20) | M2K | 5m | rth | 128 | $1,404 | $11 | 1.49 | 1.79 | $-275 | $475 | $200 | $1,204 |
| 3.1 Price momentum (12-1, time series) | MGC | 5m | tradeify | 116 | $1,308 | $11 | 0.33 | 1.15 | $-1,002 | $3,466 | $-3,125 | $4,433 |
| 8.1 Moving averages with HP filter | MGC | 5m | 24h | 121 | $1,287 | $11 | 0.36 | 1.14 | $-904 | $2,754 | $-2,109 | $3,396 |
| 3.14 Support and resistance (pivot) | MGC | 5m | tradeify | 216 | $1,170 | $5 | 0.45 | 1.18 | $-1,059 | $2,369 | $1,073 | $97 |
| 10.4 Trend following, one market | MGC | 5m | tradeify | 121 | $1,147 | $9 | 0.28 | 1.13 | $-1,208 | $4,360 | $-3,241 | $4,389 |
| 18.2 Neural network (MLP) | MNQ | 5m | rth | 95 | $1,130 | $12 | 0.75 | 1.47 | $-968 | $968 | $-620 | $1,750 |
| 4.1.1 Rotation with MA filter | portfolio | 5m | 24h | 256 | $1,066 | $4 | 0.46 | 1.18 | $-630 | $2,017 | $-2,077 | $3,142 |
| 8.1 Moving averages with HP filter | MES | 5m | 24h | 102 | $1,060 | $10 | 0.43 | 1.18 | $-842 | $2,085 | $-434 | $1,494 |
| 10.4 Trend following, one market | MES | 5m | rth | 63 | $962 | $15 | 0.36 | 1.19 | $-772 | $1,236 | $-635 | $1,597 |
| 3.14 Support and resistance (pivot) | MGC | 5m | 24h | 196 | $927 | $5 | 0.35 | 1.14 | $-1,024 | $2,463 | $1,116 | $-189 |
| 8.1 Moving averages with HP filter | MES | 5m | rth | 64 | $874 | $14 | 0.49 | 1.23 | $-712 | $1,535 | $788 | $86 |
| 3.12 Two moving averages + 2% stop | MES | 5m | 24h | 411 | $846 | $2 | 0.31 | 1.12 | $-851 | $3,921 | $-2,295 | $3,142 |
| 3.12 Two moving averages (10/30) | MES | 5m | 24h | 412 | $826 | $2 | 0.30 | 1.12 | $-851 | $3,941 | $-2,316 | $3,142 |
| 3.11 Single moving average (SMA 50) | MNQ | 5m | 24h | 833 | $820 | $1 | 0.11 | 1.05 | $-3,941 | $5,572 | $-487 | $1,307 |
| 3.11 Single moving average (SMA 50) | MNQ | 5m | tradeify | 866 | $744 | $1 | 0.10 | 1.04 | $-4,082 | $5,298 | $-543 | $1,288 |
| 3.1 Price momentum (12-1, time series) | MNQ | 5m | rth | 60 | $704 | $12 | 0.14 | 1.06 | $-1,340 | $2,700 | $-1,051 | $1,754 |
| 10.4 Trend following, one market | MGC | 5m | rth | 59 | $694 | $12 | 0.33 | 1.14 | $-610 | $1,926 | $-679 | $1,373 |
| 3.1 Price momentum (12-1, time series) | MGC | 5m | 24h | 75 | $692 | $9 | 0.18 | 1.08 | $-942 | $3,684 | $-3,217 | $3,909 |
| 3.11 Single moving average (SMA 50) | M2K | 5m | rth | 234 | $667 | $3 | 0.56 | 1.27 | $-436 | $628 | $-163 | $830 |
| 10.4 Trend following, one market | MGC | 5m | 24h | 80 | $640 | $8 | 0.16 | 1.07 | $-1,221 | $4,471 | $-3,207 | $3,847 |
| 8.1 Moving averages with HP filter | M2K | 5m | rth | 67 | $597 | $9 | 0.59 | 1.30 | $-266 | $528 | $256 | $341 |
| 3.12 Two moving averages (10/30) | MGC | 5m | rth | 160 | $580 | $4 | 0.22 | 1.11 | $-1,105 | $2,385 | $174 | $406 |
| 3.12 Two moving averages + 2% stop | MGC | 5m | rth | 160 | $580 | $4 | 0.22 | 1.11 | $-1,105 | $2,385 | $174 | $406 |
| 3.14 Support and resistance (pivot) | MGC | 5m | rth | 66 | $559 | $8 | 0.46 | 1.24 | $-405 | $1,182 | $-184 | $744 |
| 9.5 Skewness premium | portfolio | 5m | tradeify | 271 | $529 | $2 | 0.25 | 1.10 | $-923 | $2,523 | $-642 | $1,171 |
| 3.11 Single moving average (EMA 50) | M2K | 5m | rth | 257 | $528 | $2 | 0.44 | 1.21 | $-539 | $800 | $-385 | $913 |
| 9.5 Skewness premium | portfolio | 5m | rth | 162 | $456 | $3 | 0.27 | 1.13 | $-623 | $2,117 | $-1,314 | $1,769 |
| 8.1 Moving averages with HP filter | M2K | 5m | 24h | 93 | $455 | $5 | 0.34 | 1.14 | $-470 | $1,081 | $-672 | $1,126 |
| 3.15 Channel, breakout (Donchian 20) | MNQ | 5m | 24h | 379 | $448 | $1 | 0.06 | 1.03 | $-3,667 | $5,300 | $-344 | $792 |
| 8.1 Moving averages with HP filter | M2K | 5m | tradeify | 134 | $430 | $3 | 0.32 | 1.14 | $-467 | $1,242 | $-807 | $1,237 |
| 3.1 Price momentum (12-1, time series) | MES | 5m | rth | 64 | $373 | $6 | 0.14 | 1.07 | $-772 | $1,407 | $-1,072 | $1,445 |
| 9.5 Skewness premium | portfolio | 5m | 24h | 190 | $254 | $1 | 0.12 | 1.05 | $-915 | $2,486 | $-467 | $721 |
| 3.12 Two moving averages (10/30) | M2K | 5m | 24h | 423 | $144 | $0 | 0.13 | 1.05 | $-311 | $969 | $-383 | $527 |
| 3.12 Two moving averages + 2% stop | M2K | 5m | 24h | 422 | $140 | $0 | 0.13 | 1.04 | $-311 | $975 | $-380 | $521 |
| 4.1 Sector momentum rotation (long/short) | portfolio | 5m | rth | 186 | $129 | $1 | 0.06 | 1.03 | $-746 | $1,313 | $-145 | $274 |

## Buy-and-hold benchmarks

| Strategy | Market | TF | Mode | Trades | Net | Per trade | t | PF (days) | Worst day | Max DD | 1st half | 2nd half |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 Benchmark: buy and hold | M2K | 15m | 24h | 1 | $-562 | $-562 | -0.42 | 0.85 | $-700 | $1,413 | $-37 | $-525 |
| 0 Benchmark: buy and hold | M2K | 15m | rth | 42 | $-1,387 | $-33 | -1.27 | 0.57 | $-652 | $1,778 | $-72 | $-1,316 |
| 0 Benchmark: buy and hold | M2K | 15m | tradeify | 43 | $-1,189 | $-28 | -0.91 | 0.70 | $-705 | $1,830 | $-300 | $-890 |
| 0 Benchmark: buy and hold | MES | 15m | 24h | 1 | $-2,459 | $-2,459 | -0.76 | 0.73 | $-1,562 | $4,750 | $130 | $-2,589 |
| 0 Benchmark: buy and hold | MES | 15m | rth | 42 | $-4,204 | $-100 | -1.56 | 0.45 | $-1,576 | $5,044 | $-80 | $-4,124 |
| 0 Benchmark: buy and hold | MES | 15m | tradeify | 43 | $-3,800 | $-88 | -1.21 | 0.61 | $-1,573 | $5,584 | $-410 | $-3,390 |
| 0 Benchmark: buy and hold | MGC | 15m | 24h | 1 | $-5,517 | $-5,517 | -1.36 | 0.58 | $-1,912 | $7,120 | $-1,003 | $-4,514 |
| 0 Benchmark: buy and hold | MGC | 15m | rth | 42 | $-4,831 | $-115 | -2.25 | 0.39 | $-745 | $6,001 | $-1,151 | $-3,680 |
| 0 Benchmark: buy and hold | MGC | 15m | tradeify | 43 | $-7,578 | $-176 | -1.90 | 0.45 | $-1,973 | $8,537 | $-1,622 | $-5,956 |
| 0 Benchmark: buy and hold | MNQ | 15m | 24h | 1 | $-8,295 | $-8,295 | -1.18 | 0.64 | $-2,489 | $12,708 | $-1,105 | $-7,190 |
| 0 Benchmark: buy and hold | MNQ | 15m | rth | 42 | $-8,804 | $-210 | -1.61 | 0.48 | $-2,712 | $10,692 | $-392 | $-8,412 |
| 0 Benchmark: buy and hold | MNQ | 15m | tradeify | 43 | $-11,449 | $-266 | -1.69 | 0.53 | $-2,506 | $14,692 | $-2,326 | $-9,123 |
| 0 Benchmark: buy and hold | M2K | 1d | 24h | 1 | $6,543 | $6,543 | 0.97 | 1.06 | $-832 | $3,984 | $1,657 | $4,886 |
| 0 Benchmark: buy and hold | M2K | 1d | tradeify | 1 | $-5,812 | $-5,812 | -0.88 | 0.95 | $-766 | $10,261 | $204 | $-6,016 |
| 0 Benchmark: buy and hold | MES | 1d | 24h | 1 | $30,531 | $30,531 | 2.48 | 1.13 | $-1,688 | $5,988 | $8,863 | $21,668 |
| 0 Benchmark: buy and hold | MES | 1d | tradeify | 1 | $-2,067 | $-2,067 | -0.17 | 0.99 | $-1,779 | $9,397 | $-6,508 | $4,441 |
| 0 Benchmark: buy and hold | MGC | 1d | 24h | 1 | $24,932 | $24,932 | 1.38 | 1.08 | $-5,733 | $18,030 | $818 | $24,114 |
| 0 Benchmark: buy and hold | MGC | 1d | tradeify | 1 | $-36,262 | $-36,262 | -2.13 | 0.88 | $-6,656 | $36,707 | $-21,537 | $-14,725 |
| 0 Benchmark: buy and hold | MNQ | 1d | 24h | 1 | $48,797 | $48,797 | 2.20 | 1.13 | $-3,630 | $12,714 | $11,547 | $37,250 |
| 0 Benchmark: buy and hold | MNQ | 1d | tradeify | 1 | $19,292 | $19,292 | 0.90 | 1.05 | $-3,827 | $15,018 | $-114 | $19,407 |
| 0 Benchmark: buy and hold | M2K | 1h | 24h | 1 | $1,413 | $1,413 | 0.37 | 1.04 | $-700 | $3,593 | $180 | $1,233 |
| 0 Benchmark: buy and hold | M2K | 1h | rth | 503 | $-3,463 | $-7 | -1.39 | 0.85 | $-475 | $4,134 | $-1,302 | $-2,161 |
| 0 Benchmark: buy and hold | M2K | 1h | tradeify | 495 | $-811 | $-2 | -0.22 | 0.97 | $-657 | $3,633 | $-1,242 | $431 |
| 0 Benchmark: buy and hold | MES | 1h | 24h | 1 | $5,993 | $5,993 | 0.77 | 1.10 | $-1,562 | $6,145 | $3,831 | $2,162 |
| 0 Benchmark: buy and hold | MES | 1h | rth | 500 | $-3,491 | $-7 | -0.71 | 0.91 | $-1,126 | $5,410 | $-332 | $-3,159 |
| 0 Benchmark: buy and hold | MES | 1h | tradeify | 495 | $2,303 | $5 | 0.31 | 1.04 | $-1,465 | $5,638 | $1,863 | $440 |
| 0 Benchmark: buy and hold | MGC | 1h | 24h | 1 | $9,691 | $9,691 | 0.66 | 1.08 | $-3,467 | $20,744 | $15,250 | $-5,559 |
| 0 Benchmark: buy and hold | MGC | 1h | rth | 504 | $-13,007 | $-26 | -1.76 | 0.78 | $-3,633 | $17,102 | $2,062 | $-15,069 |
| 0 Benchmark: buy and hold | MGC | 1h | tradeify | 496 | $1,180 | $2 | 0.08 | 1.01 | $-3,345 | $21,545 | $10,894 | $-9,714 |
| 0 Benchmark: buy and hold | MNQ | 1h | 24h | 1 | $10,651 | $10,651 | 0.67 | 1.08 | $-2,489 | $12,708 | $8,417 | $2,234 |
| 0 Benchmark: buy and hold | MNQ | 1h | rth | 500 | $-1,869 | $-4 | -0.20 | 0.98 | $-2,207 | $9,137 | $838 | $-2,707 |
| 0 Benchmark: buy and hold | MNQ | 1h | tradeify | 493 | $3,171 | $6 | 0.21 | 1.02 | $-2,430 | $16,102 | $5,561 | $-2,390 |
| 0 Benchmark: buy and hold | M2K | 5m | 24h | 1 | $-566 | $-566 | -0.42 | 0.85 | $-700 | $1,413 | $-37 | $-528 |
| 0 Benchmark: buy and hold | M2K | 5m | rth | 42 | $-1,272 | $-30 | -1.19 | 0.60 | $-620 | $1,717 | $-111 | $-1,161 |
| 0 Benchmark: buy and hold | M2K | 5m | tradeify | 43 | $-1,189 | $-28 | -0.90 | 0.70 | $-713 | $1,831 | $-308 | $-881 |
| 0 Benchmark: buy and hold | MES | 5m | 24h | 1 | $-2,460 | $-2,460 | -0.76 | 0.73 | $-1,562 | $4,750 | $128 | $-2,589 |
| 0 Benchmark: buy and hold | MES | 5m | rth | 42 | $-3,964 | $-94 | -1.53 | 0.45 | $-1,509 | $4,819 | $-195 | $-3,769 |
| 0 Benchmark: buy and hold | MES | 5m | tradeify | 43 | $-3,867 | $-90 | -1.21 | 0.61 | $-1,588 | $5,654 | $-372 | $-3,495 |
| 0 Benchmark: buy and hold | MGC | 5m | 24h | 1 | $-5,525 | $-5,525 | -1.36 | 0.58 | $-1,912 | $7,120 | $-1,011 | $-4,514 |
| 0 Benchmark: buy and hold | MGC | 5m | rth | 42 | $-4,320 | $-103 | -2.06 | 0.43 | $-670 | $5,533 | $-1,054 | $-3,266 |
| 0 Benchmark: buy and hold | MGC | 5m | tradeify | 43 | $-7,236 | $-168 | -1.82 | 0.47 | $-2,000 | $8,248 | $-1,526 | $-5,710 |
| 0 Benchmark: buy and hold | MNQ | 5m | 24h | 1 | $-8,305 | $-8,305 | -1.18 | 0.64 | $-2,489 | $12,708 | $-1,130 | $-7,174 |
| 0 Benchmark: buy and hold | MNQ | 5m | rth | 42 | $-8,196 | $-195 | -1.55 | 0.48 | $-2,618 | $9,941 | $-719 | $-7,477 |
| 0 Benchmark: buy and hold | MNQ | 5m | tradeify | 43 | $-11,573 | $-269 | -1.70 | 0.53 | $-2,531 | $14,761 | $-2,224 | $-9,349 |

## Not testable with these four futures

- **2.2-2.57 Options strategies (57):** need option prices and implied volatility
- **3.2 Earnings momentum, 3.3 Value, 3.5 Implied vol, 3.6 Multifactor, 3.7 Residual momentum:** need stock fundamentals, options or a stock cross-section
- **3.8 Pairs trading, 3.9.1 / 3.10 Mean-reversion (multi-cluster, weighted):** need a large stock universe with industry clusters
- **3.16 M&A, 3.18 Stat-arb optimization, 3.19 Market-making, 3.20 Alpha combos:** need deal data, a stock universe or order-book data
- **4.2 Alpha rotation, 4.3 R-squared:** need Fama-French / Carhart factor returns (not reachable from this network)
- **4.5 Leveraged ETFs:** need leveraged ETF pairs
- **5.x Fixed income (15):** need bond prices, yield curves, CDS and swaps
- **6.2-6.4 Index arbitrage, dispersion, ETF arbitrage:** need index constituents, options or ETF quotes
- **7.x Volatility (8):** need VIX futures, ETNs, options or variance swaps
- **8.2-8.5 FX carry and triangular arbitrage:** need interest rates and FX crosses
- **9.1 Roll yields, 10.2 Calendar spread:** need the second-month contract (only continuous front month is available)
- **9.2 Hedging pressure:** needs CFTC COT data (cftc.gov is not reachable from this network)
- **10.1 Hedging, cross-hedging, rate hedging:** hedging methods, not return strategies
- **10.3.1 Contrarian with market activity:** needs open interest history
- **11-17 Structured, convertibles, tax, misc, distressed, real estate, cash:** not tradable with futures (17.2 and 17.6 are illegal activities the book describes, not strategies)
- **18.3 Sentiment (naive Bayes):** needs tweet / text data
- **19.2-19.4 Global macro:** need macro and inflation series
- **19.5 Economic announcements:** needs an FOMC date list (federalreserve.gov is not reachable from this network)
- **20 Infrastructure:** not tradable with futures
