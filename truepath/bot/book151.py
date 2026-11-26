"""Backtest every strategy in Kakushadze & Serur, "151 Trading Strategies" (SSRN 3247865, 2018)
that can be traded with MES, MNQ, M2K (RTY) and MGC futures.

Prices: full-size ES, NQ, RTY, GC continuous contracts from OpenBB/yfinance (same prices as the
micros, much longer history); P&L in micro dollars: MES $5, MNQ $2, M2K $5, MGC $10 per point.
Costs: $1.55 per contract per side + 2 ticks slippage per side. Signals at a bar's close fill at
the next bar's open. Parameters are the book's own examples; where it gives none, one value was
fixed before any run (marked "chosen"). Nothing is tuned.

Timeframes: 1d (2000+, RTY 2017+), 1h (2 years), 15m and 5m (~60 days). Intraday runs twice:
"24h" exactly as written, and "rth" flat outside 09:30-15:55 ET (what a Tradeify account can trade).

    python truepath/bot/book151.py            # writes trader/book151_results.csv and .json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "trader" / "data"
MARKETS = {  # data file root -> (micro name, $ per point, tick)
    "ES": ("MES", 5.0, 0.25), "NQ": ("MNQ", 2.0, 0.25), "RTY": ("M2K", 5.0, 0.10), "GC": ("MGC", 10.0, 0.10),
}
COMMISSION_SIDE, SLIP_TICKS = 1.55, 2
TIMEFRAMES = ["1d", "1h", "15m", "5m"]
PUBLISHED = pd.Timestamp("2018-09-01", tz="America/New_York")


# ══════════════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════════════

def load(root: str, tf: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{root}_{tf}.csv", index_col=0)
    idx = pd.to_datetime(df.index)
    idx = idx.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT") if idx.tz is None else idx.tz_convert("America/New_York")
    df.index = idx
    df = df[df.index.notna()][["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated()].sort_index().dropna(subset=["open", "high", "low", "close"])
    if tf == "1d":
        df = df[df.index >= pd.Timestamp("2010-01-01", tz="America/New_York")]
    return df[(df["close"] > 0) & (df["high"] >= df["low"])]


def rth_mask(idx: pd.DatetimeIndex, tf: str) -> np.ndarray:
    """allowed[t] is True if the bar AFTER t sits inside 09:30-15:55 ET on the same day."""
    if tf == "1d":
        return np.ones(len(idx), bool)
    mins = {"1h": 60, "15m": 15, "5m": 5}[tf]
    start = idx.hour * 60 + idx.minute
    ok = (start >= 570) & (start + mins <= 955)
    nxt = np.append(ok[1:], False)
    same_day = np.append(idx.date[1:] == idx.date[:-1], False)
    return nxt & same_day


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def hold(entry_long: np.ndarray, exit_long: np.ndarray, entry_short: np.ndarray, exit_short: np.ndarray) -> np.ndarray:
    """State machine for 'establish / liquidate' rules. Entry of the other side flips the position."""
    pos = np.zeros(len(entry_long))
    p = 0.0
    for i in range(len(pos)):
        if p > 0 and exit_long[i]:
            p = 0.0
        elif p < 0 and exit_short[i]:
            p = 0.0
        if entry_long[i] and p <= 0 and not exit_long[i]:
            p = 1.0
        elif entry_short[i] and p >= 0 and not exit_short[i]:
            p = -1.0
        pos[i] = p
    return pos


def every(n: int, length: int) -> np.ndarray:
    m = np.zeros(length, bool)
    m[::n] = True
    return m


def hold_weights(w: pd.DataFrame, rebalance: int) -> pd.DataFrame:
    """Rebalance every `rebalance` bars and hold the weights in between."""
    keep = every(rebalance, len(w))
    return w.where(pd.Series(keep, index=w.index), np.nan).ffill().fillna(0.0)


def prev_session_hlc(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    if tf == "1d":
        return df[["high", "low", "close"]].shift(1)
    day = pd.Series(df.index.date, index=df.index)
    g = df.groupby(day.values)
    d = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()}).shift(1)
    return d.reindex(day.values).set_axis(df.index)


def hp_trend_last(y: np.ndarray, lam: float) -> float:
    """One-sided HP filter: fit on the trailing window, keep only its last point (no look-ahead)."""
    from scipy.sparse import diags, identity
    from scipy.sparse.linalg import spsolve
    n = len(y)
    d = diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(n - 2, n))
    return float(spsolve((identity(n) + lam * (d.T @ d)).tocsc(), y)[-1])


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-CONTRACT STRATEGIES  (df -> target position at each bar's close, in contracts)
# ══════════════════════════════════════════════════════════════════════════════

def s_price_momentum(df, tf):              # 3.1, time-series form: 12-1 formation, 1-month hold (book: T=12, S=1)
    c = df["close"]
    r = c.shift(21) / c.shift(252) - 1
    return hold_weights(pd.DataFrame({"x": np.sign(r)}), 21)["x"].to_numpy()


def s_single_sma(df, tf):                  # 3.11 SMA; T=50 chosen
    c = df["close"]
    return np.sign(c - c.rolling(50).mean()).fillna(0).to_numpy()


def s_single_ema(df, tf):                  # 3.11 EMA; T=50 chosen
    c = df["close"]
    return np.sign(c - c.ewm(span=50, adjust=False).mean()).to_numpy()


def s_two_ma(df, tf):                      # 3.12; T'=10, T=30 (book)
    c = df["close"]
    return np.sign(c.rolling(10).mean() - c.rolling(30).mean()).fillna(0).to_numpy()


def s_two_ma_stop(df, tf):                 # 3.12 Eq. 323; delta = 2% (book)
    c = df["close"]
    up = (c.rolling(10).mean() > c.rolling(30).mean()).to_numpy()
    dn = (c.rolling(10).mean() < c.rolling(30).mean()).to_numpy()
    p1 = c.shift(1).to_numpy()
    cv = c.to_numpy()
    # once stopped, wait for a fresh cross before re-entering
    fresh_up = up & ~np.roll(up, 1)
    fresh_dn = dn & ~np.roll(dn, 1)
    return hold(fresh_up, cv < 0.98 * p1, fresh_dn, cv > 1.02 * p1)


def s_three_ma(df, tf):                    # 3.13; 3 / 10 / 21 (book)
    c = df["close"]
    m1, m2, m3 = (c.rolling(n).mean().to_numpy() for n in (3, 10, 21))
    return hold((m1 > m2) & (m2 > m3), m1 <= m2, (m1 < m2) & (m2 < m3), m1 >= m2)


def s_support_resistance(df, tf):          # 3.14; previous day's pivot; one round per side per day
    hlc = prev_session_hlc(df, tf)
    cpiv = (hlc["high"] + hlc["low"] + hlc["close"]) / 3
    r, s = 2 * cpiv - hlc["low"], 2 * cpiv - hlc["high"]
    p = df["close"]
    day = df.index.date
    pos, cur, used_l, used_s, last_day = np.zeros(len(df)), 0.0, False, False, None
    P, C, R, S = p.to_numpy(), cpiv.to_numpy(), r.to_numpy(), s.to_numpy()
    for i in range(len(df)):
        if tf != "1d" and day[i] != last_day:
            used_l = used_s = False
            last_day = day[i]
        if np.isnan(C[i]):
            pos[i] = 0
            continue
        if cur > 0 and P[i] >= R[i]:
            cur, used_l = 0.0, True
        elif cur < 0 and P[i] <= S[i]:
            cur, used_s = 0.0, True
        if P[i] > C[i] and cur <= 0 and not used_l and P[i] < R[i]:
            cur = 1.0
        elif P[i] < C[i] and cur >= 0 and not used_s and P[i] > S[i]:
            cur = -1.0
        if tf == "1d":
            used_l = used_s = False
        pos[i] = cur
    return pos


def s_channel_fade(df, tf):                # 3.15 as written: buy the floor, sell the ceiling; T=20 chosen
    c = df["close"]
    lo, hi = c.shift(1).rolling(20).min(), c.shift(1).rolling(20).max()
    at_floor, at_ceil = (c <= lo).to_numpy(), (c >= hi).to_numpy()
    return hold(at_floor, at_ceil, at_ceil, at_floor)


def s_channel_breakout(df, tf):            # 3.15 text: a break through the channel starts a trend; T=20
    c = df["close"]
    lo, hi = c.shift(1).rolling(20).min(), c.shift(1).rolling(20).max()
    up, dn = (c > hi).to_numpy(), (c < lo).to_numpy()
    return hold(up, dn, dn, up)


def s_knn(df, tf):                         # 3.17; k=10, 5-bar target, 500-bar training window (chosen)
    c, v = df["close"], df["volume"].replace(0, np.nan)
    feats = pd.DataFrame({
        "vol": v.rolling(10).mean() / v.rolling(50).mean(),
        "p10": c / c.rolling(10).mean() - 1,
        "p30": c / c.rolling(30).mean() - 1,
        "p100": c / c.rolling(100).mean() - 1,
    })  # the book's MAs, taken relative to price so neighbours are not just similar price levels
    y = (c.shift(-5) / c - 1).to_numpy()
    X = feats.to_numpy()
    n, W, H, k = len(df), 500, 5, 10
    pos = np.zeros(n)
    for t in range(W + H + 100, n):
        lo = t - W - H
        train = slice(lo, t - H)                      # targets fully known at t
        Xt, yt = X[train], y[train]
        good = ~np.isnan(Xt).any(1) & ~np.isnan(yt)
        if good.sum() < 50 or np.isnan(X[t]).any():
            continue
        Xt, yt = Xt[good], yt[good]
        mn, mx = Xt.min(0), Xt.max(0)
        span = np.where(mx > mn, mx - mn, 1)
        d = (((Xt - mn) / span - (X[t] - mn) / span) ** 2).sum(1)
        pred = yt[np.argpartition(d, k)[:k]].mean()
        pos[t] = np.sign(pred)
    return hold_weights(pd.DataFrame({"x": pos}), H)["x"].to_numpy()


def s_ibs(df, tf):                         # 4.4 IBS, single-market form: long < 0.2, short > 0.8, 1-bar hold
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    ibs = ((df["close"] - df["low"]) / rng).fillna(0.5)
    return np.where(ibs < 0.2, 1.0, np.where(ibs > 0.8, -1.0, 0.0))


def s_vol_target(df, tf):                  # 6.5; 15% target, 20-bar vol, cap 2x, rebalance if |dw|/w > 20% (chosen)
    bars = {"1d": 252, "1h": 23 * 252, "15m": 92 * 252, "5m": 276 * 252}[tf]
    r = df["close"].pct_change()
    w = (0.15 / (r.rolling(20).std() * math.sqrt(bars))).clip(upper=2.0).fillna(0).to_numpy()
    out, cur = np.zeros(len(w)), 0.0
    for i, x in enumerate(w):
        if cur == 0 or abs(x - cur) / cur > 0.2:
            cur = x
        out[i] = cur
    return out


def s_hp_ma(df, tf):                       # 8.1; HP lambda = 100 n^2 (n = bars/yr), 252-bar window, MA 10/30 of the trend
    bars = {"1d": 252, "1h": 23 * 252, "15m": 92 * 252, "5m": 276 * 252}[tf]
    lam = min(100.0 * bars ** 2, 1e10)
    y = np.log(df["close"].to_numpy())
    trend = np.full(len(y), np.nan)
    step = 1 if tf in ("1d", "1h") else 3   # refit every 3 bars on 5m/15m to keep the run time sane
    last = np.nan
    for t in range(252, len(y)):
        if (t - 252) % step == 0:
            last = hp_trend_last(y[t - 252 + 1: t + 1], lam)
        trend[t] = last
    tr = pd.Series(trend)
    return np.sign(tr.rolling(10).mean() - tr.rolling(30).mean()).fillna(0).to_numpy()


def s_ou(df, tf):                          # 9.6; OU fitted on trailing 252 bars (AR(1) on log price), |z| > 1 in, z = 0 out
    x = np.log(df["close"])
    xl = x.shift(1)
    cov = x.rolling(252).cov(xl)
    var = xl.rolling(252).var()
    b = (cov / var).clip(upper=0.9999)
    a = x.rolling(252).mean() - b * xl.rolling(252).mean()
    mu = a / (1 - b)
    resid_sd = (x - (a + b * xl)).rolling(252).std()
    sd_eq = resid_sd / np.sqrt(1 - b ** 2)
    z = ((x - mu) / sd_eq).to_numpy()
    z = np.nan_to_num(z)
    return hold(z < -1, z >= 0, z > 1, z <= 0)


def s_trend_sign(df, tf):                  # 10.4 for one market: sign of the trailing 252-bar return, monthly hold
    c = df["close"]
    return hold_weights(pd.DataFrame({"x": np.sign(c / c.shift(252) - 1)}), 21)["x"].to_numpy()


def s_ann(df, tf):                         # 18.2; MLP on EMAs/EMSDs of normalized returns + RSI, walk-forward
    from sklearn.neural_network import MLPClassifier
    c = df["close"]
    r = c.pct_change()
    rn = (r - r.rolling(50).mean().shift(1)) / r.rolling(50).std().shift(1)
    f = {}
    for s in (3, 10, 30):
        f[f"ema{s}"] = rn.ewm(span=s, adjust=False).mean()
        f[f"emsd{s}"] = rn.ewm(span=s, adjust=False).std()
    delta = c.diff()
    up, dn = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(), (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi"] = (100 - 100 / (1 + up / dn.replace(0, np.nan))) / 100
    X = pd.DataFrame(f).to_numpy()
    y = (c.shift(-1) > c).astype(int).to_numpy()
    n, pos = len(df), np.zeros(len(df))
    start, step = 1000, 250
    for t0 in range(start, n, step):
        tr = slice(max(60, t0 - 3000), t0 - 1)
        Xt, yt = X[tr], y[tr]
        ok = ~np.isnan(Xt).any(1)
        if ok.sum() < 300:
            continue
        m = MLPClassifier(hidden_layer_sizes=(16,), max_iter=300, random_state=0)
        m.fit(Xt[ok], yt[ok])
        te = slice(t0, min(n, t0 + step))
        Xe = X[te]
        okc = ~np.isnan(Xe).any(1)
        pr = np.full(len(Xe), 0.5)
        if okc.any():
            pr[okc] = m.predict_proba(Xe[okc])[:, 1]
        pos[te] = np.where(pr > 0.55, 1.0, np.where(pr < 0.45, -1.0, 0.0))
    return pos


def s_buy_hold(df, tf):                    # benchmark, not a book strategy: always long 1 contract
    return np.ones(len(df))


SINGLE = {
    "0 Benchmark: buy and hold": s_buy_hold,
    "3.1 Price momentum (12-1, time series)": s_price_momentum,
    "3.11 Single moving average (SMA 50)": s_single_sma,
    "3.11 Single moving average (EMA 50)": s_single_ema,
    "3.12 Two moving averages (10/30)": s_two_ma,
    "3.12 Two moving averages + 2% stop": s_two_ma_stop,
    "3.13 Three moving averages (3/10/21)": s_three_ma,
    "3.14 Support and resistance (pivot)": s_support_resistance,
    "3.15 Channel, fade (Donchian 20)": s_channel_fade,
    "3.15 Channel, breakout (Donchian 20)": s_channel_breakout,
    "3.17 Single-asset KNN": s_knn,
    "4.4 Mean-reversion (IBS)": s_ibs,
    "6.5 Volatility targeting (15%)": s_vol_target,
    "8.1 Moving averages with HP filter": s_hp_ma,
    "9.6 Pricing model (OU mean-reversion)": s_ou,
    "10.4 Trend following, one market": s_trend_sign,
    "18.2 Neural network (MLP)": s_ann,
}


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO STRATEGIES  (panel of closes -> weights per market, sum |w| = 1 unless stated)
# ══════════════════════════════════════════════════════════════════════════════

def norm(w: pd.DataFrame) -> pd.DataFrame:
    s = w.abs().sum(1).replace(0, np.nan)
    return w.div(s, axis=0).fillna(0.0)


def rank_long_short(score: pd.DataFrame, long_high: bool = True) -> pd.DataFrame:
    """Top market long, bottom market short (decile/quintile of a 4-market universe = 1 market)."""
    r = score.rank(axis=1, ascending=not long_high)
    w = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    w[r.eq(1)] = 0.5
    w[r.eq(score.notna().sum(1), axis=0)] = -0.5
    return w.where(score.notna().sum(1) >= 3, 0.0, axis=0)


def p_low_vol(c):          # 3.4; 252-bar vol, long lowest, short highest, monthly
    vol = c.pct_change().rolling(252).std()
    return hold_weights(rank_long_short(vol, long_high=False), 21)


def p_mean_rev_cluster(c):  # 3.9; one cluster (all 4), w = -(R - mean R), 1-bar returns, rebalance every bar
    r = c.pct_change()
    return norm(-(r.sub(r.mean(1), axis=0))).fillna(0)


def p_sector_rotation(c):  # 4.1; 6-month formation, 1-month hold, long top / short bottom
    return hold_weights(rank_long_short(c / c.shift(126) - 1), 21)


def p_sector_rotation_long(c):  # 4.1 long-only: top market only
    r = (c / c.shift(126) - 1).rank(axis=1, ascending=False)
    return hold_weights((r == 1).astype(float).where((c / c.shift(126)).notna().sum(1) >= 3, 0.0, axis=0), 21)


def p_rotation_ma(c):      # 4.1.1; long top only if P > MA200, short bottom only if P < MA200
    w = rank_long_short(c / c.shift(126) - 1)
    ma = c.rolling(200).mean()
    w = w.where(~((w > 0) & (c <= ma)), 0.0).where(~((w < 0) & (c >= ma)), 0.0)
    return hold_weights(w, 21)


def p_dual_momentum(c):    # 4.1.2; best equity index if ES > MA200, else gold
    eq = [m for m in ("ES", "NQ", "RTY") if m in c]
    r = (c[eq] / c[eq].shift(126) - 1).rank(axis=1, ascending=False)
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    w[eq] = (r == 1).astype(float)
    risk_off = c["ES"] <= c["ES"].rolling(200).mean()
    w.loc[risk_off, eq] = 0.0
    w.loc[risk_off, "GC"] = 1.0
    w = w.where(c["ES"].rolling(200).mean().notna(), 0.0, axis=0)
    return hold_weights(w, 21)


def _multi_trend(c, power):  # 4.6; positive 252-bar return and above MA200; w ~ R / sigma^power, long only
    rc = c / c.shift(252) - 1
    sig = c.pct_change().rolling(252).std()
    keep = (rc > 0) & (c > c.rolling(200).mean())
    w = (rc / sig ** power).where(keep, 0.0)
    return hold_weights(norm(w), 21)


def p_multi_trend_1(c): return _multi_trend(c, 0)
def p_multi_trend_2(c): return _multi_trend(c, 1)
def p_multi_trend_3(c): return _multi_trend(c, 2)


def p_diversify(c):        # 9.3 passive: 50/50 S&P + gold, monthly rebalance
    w = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    w["ES"], w["GC"] = 0.5, 0.5
    return hold_weights(w, 21)


def p_value(c):            # 9.4; v = P(5y ago)/P(now), long top, short bottom, monthly (daily data only)
    return hold_weights(rank_long_short(c.shift(1260) / c), 21)


def p_skew(c):             # 9.5; 252-bar skewness, long lowest, short highest, monthly
    return hold_weights(rank_long_short(c.pct_change().rolling(252).skew(), long_high=False), 21)


def p_contrarian(c):       # 10.3; weekly (5-bar) returns vs equal-weight market, weekly rebalance
    r = c / c.shift(5) - 1
    return hold_weights(norm(-(r.sub(r.mean(1), axis=0))), 5)


def p_trend_portfolio(c):  # 10.4; w ~ sign(R_252) / sigma, sum |w| = 1, monthly
    r = c / c.shift(252) - 1
    sig = c.pct_change().rolling(252).std()
    return hold_weights(norm(np.sign(r) / sig), 21)


PORTFOLIO = {
    "3.4 Low-volatility anomaly": p_low_vol,
    "3.9 Mean-reversion, single cluster": p_mean_rev_cluster,
    "4.1 Sector momentum rotation (long/short)": p_sector_rotation,
    "4.1 Sector momentum rotation (long only)": p_sector_rotation_long,
    "4.1.1 Rotation with MA filter": p_rotation_ma,
    "4.1.2 Dual-momentum rotation": p_dual_momentum,
    "4.6 Multi-asset trend, w ~ R": p_multi_trend_1,
    "4.6 Multi-asset trend, w ~ R/sigma": p_multi_trend_2,
    "4.6 Multi-asset trend, w ~ R/sigma^2": p_multi_trend_3,
    "9.3 Diversification with commodities (passive)": p_diversify,
    "9.4 Value (5-year)": p_value,
    "9.5 Skewness premium": p_skew,
    "10.3 Contrarian trading": p_contrarian,
    "10.4 Trend following (portfolio)": p_trend_portfolio,
}

NOT_TESTABLE = {
    "2.2-2.57 Options strategies (57)": "need option prices and implied volatility",
    "3.2 Earnings momentum, 3.3 Value, 3.5 Implied vol, 3.6 Multifactor, 3.7 Residual momentum": "need stock fundamentals, options or a stock cross-section",
    "3.8 Pairs trading, 3.9.1 / 3.10 Mean-reversion (multi-cluster, weighted)": "need a large stock universe with industry clusters",
    "3.16 M&A, 3.18 Stat-arb optimization, 3.19 Market-making, 3.20 Alpha combos": "need deal data, a stock universe or order-book data",
    "4.2 Alpha rotation, 4.3 R-squared": "need Fama-French / Carhart factor returns (not reachable from this network)",
    "4.5 Leveraged ETFs": "need leveraged ETF pairs",
    "5.x Fixed income (15)": "need bond prices, yield curves, CDS and swaps",
    "6.2-6.4 Index arbitrage, dispersion, ETF arbitrage": "need index constituents, options or ETF quotes",
    "7.x Volatility (8)": "need VIX futures, ETNs, options or variance swaps",
    "8.2-8.5 FX carry and triangular arbitrage": "need interest rates and FX crosses",
    "9.1 Roll yields, 10.2 Calendar spread": "need the second-month contract (only continuous front month is available)",
    "9.2 Hedging pressure": "needs CFTC COT data (cftc.gov is not reachable from this network)",
    "10.1 Hedging, cross-hedging, rate hedging": "hedging methods, not return strategies",
    "10.3.1 Contrarian with market activity": "needs open interest history",
    "11-17 Structured, convertibles, tax, misc, distressed, real estate, cash": "not tradable with futures (17.2 and 17.6 are illegal activities the book describes, not strategies)",
    "18.3 Sentiment (naive Bayes)": "needs tweet / text data",
    "19.2-19.4 Global macro": "need macro and inflation series",
    "19.5 Economic announcements": "needs an FOMC date list (federalreserve.gov is not reachable from this network)",
    "20 Infrastructure": "not tradable with futures",
}


# ══════════════════════════════════════════════════════════════════════════════
# P&L
# ══════════════════════════════════════════════════════════════════════════════

def pnl_series(df: pd.DataFrame, pos: np.ndarray, root: str) -> pd.Series:
    """Position decided at bar t's close is held from bar t+1's open."""
    _, pv, tick = MARKETS[root]
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    p = np.nan_to_num(np.asarray(pos, float))
    prev = np.concatenate([[0, 0], p[:-2]])   # held through the gap into bar i (decided two closes ago)
    cur = np.concatenate([[0], p[:-1]])       # filled at bar i's open
    gap = np.concatenate([[0], o[1:] - c[:-1]])
    pnl = prev * gap + cur * (c - o)
    cost = np.abs(cur - prev) * (COMMISSION_SIDE + SLIP_TICKS * tick * pv)
    return pd.Series((pnl * pv - cost), index=df.index)


def count_trades(pos: np.ndarray) -> int:
    s = np.sign(np.nan_to_num(np.asarray(pos, float)))
    return int(((s != 0) & (s != np.concatenate([[0], s[:-1]]))).sum())


def stats(pnl: pd.Series, trades: int) -> dict:
    day = pnl.groupby(pnl.index.date).sum()
    day = day[day != 0]
    net = float(pnl.sum())
    if len(day) < 5:
        return {"trades": trades, "days": len(day), "net": round(net, 2)}
    sd = day.std(ddof=1)
    gw, gl = day[day > 0].sum(), -day[day < 0].sum()
    eq = day.cumsum()
    return {"trades": trades, "days": int(len(day)), "net": round(net, 2),
            "expectancy": round(net / trades, 2) if trades else None,
            "t_stat": round(float(day.mean() / (sd / math.sqrt(len(day)))), 2) if sd > 0 else None,
            "pf_days": round(float(gw / gl), 2) if gl > 0 else None,
            "win_days": round(float((day > 0).mean()), 3), "worst_day": round(float(day.min()), 2),
            "max_dd": round(float((eq.cummax().clip(lower=0) - eq).max()), 2)}


def halves(pnl: pd.Series, tf: str) -> tuple[pd.Series, pd.Series, str]:
    if tf == "1d":
        return pnl[pnl.index < PUBLISHED], pnl[pnl.index >= PUBLISHED], "pre/post publication (Sep 2018)"
    mid = pnl.index[len(pnl) // 2]
    return pnl[pnl.index < mid], pnl[pnl.index >= mid], "first/second half"


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def run() -> pd.DataFrame:
    rows = []
    for tf in TIMEFRAMES:
        frames = {m: load(m, tf) for m in MARKETS}
        modes = ["24h"] if tf == "1d" else ["24h", "rth"]
        # single-contract strategies
        for name, fn in SINGLE.items():
            for m, df in frames.items():
                try:
                    raw = np.asarray(fn(df, tf), float)
                except Exception as e:
                    rows.append({"strategy": name, "market": MARKETS[m][0], "tf": tf, "mode": "-", "error": str(e)})
                    continue
                for mode in modes:
                    pos = raw * rth_mask(df.index, tf) if mode == "rth" else raw
                    rows.append(row(name, MARKETS[m][0], tf, mode, df, {m: pos}, {m: df}))
            print(f"{tf:4} {name}", flush=True)
        # portfolio strategies on the aligned panel
        panel = pd.concat({m: f["close"] for m, f in frames.items()}, axis=1).dropna()
        aligned = {m: f.loc[panel.index] for m, f in frames.items()}
        for name, fn in PORTFOLIO.items():
            if name.startswith("9.4") and tf != "1d":
                continue
            w = fn(panel)
            for mode in modes:
                mask = rth_mask(panel.index, tf) if mode == "rth" else np.ones(len(panel), bool)
                pos = {m: w[m].to_numpy() * mask for m in w.columns}
                rows.append(row(name, "portfolio", tf, mode, panel, pos, aligned))
            print(f"{tf:4} {name}", flush=True)
    return pd.DataFrame(rows)


def row(name, market, tf, mode, df, positions: dict, frames: dict) -> dict:
    total = sum(pnl_series(frames[m], positions[m], m) for m in positions)
    trades = sum(count_trades(positions[m]) for m in positions)
    a, b, split = halves(total, tf)
    rec = {"strategy": name, "market": market, "tf": tf, "mode": mode,
           "start": str(df.index[0].date()), "end": str(df.index[-1].date()), **stats(total, trades)}
    rec["first_net"], rec["second_net"], rec["split"] = round(float(a.sum()), 2), round(float(b.sum()), 2), split
    sb = stats(b, max(1, count_trades(np.sign(sum(np.abs(positions[m]) for m in positions))[len(a):])))
    rec["second_t"] = sb.get("t_stat")
    return rec


def main() -> None:
    res = run()
    out = ROOT / "trader" / "book151_results.csv"
    res.to_csv(out, index=False)
    (ROOT / "trader" / "book151_not_testable.json").write_text(json.dumps(NOT_TESTABLE, indent=2))
    print(f"wrote {out} ({len(res)} tests)")


if __name__ == "__main__":
    main()
