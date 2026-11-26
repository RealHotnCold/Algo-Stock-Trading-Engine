"""Historical replay (decisions made bar by bar, no look-ahead) and what-if scenarios on a data window."""
import numpy as np
from ..backtesting.engine import backtest, metrics
from ..strategy.meta import NAMES, ACT
from ..strategy.regime import NAMES as REG

def bounds(S, n, period):
    matches = n == S.split["test"][1] + 1
    if period == "all": return S.split["train"][0], n - 1, False
    if matches: lo, hi = S.split[period]; return lo, hi, period == "test"
    return (int(n * 0.8), n - 1, False) if period == "test" else (int(n * 0.6), int(n * 0.8), False)

def window(S, df, period, offset, n_bars):
    lo0, hi0, oos = bounds(S, len(df), period); lo = min(lo0 + max(0, offset), hi0 - 50); hi = min(lo + n_bars, hi0)
    return lo, hi, oos, lo0, hi0

def run_window(S, df, lo, hi, cfg, sp, record=None):
    P = S.prep(df); mlo = max(0, lo - S.M)
    def decide(i, pos):
        d = S.step(P, i, pos, lo=mlo)
        if record is not None: record[i] = dict(regime=REG[d["regime"]], decision=d["label"], confidence=round(float(d["conf"]), 3), agents={n: ACT[int(a.argmax())] for n, a in zip(NAMES, d["A"])})
        return d["target"]
    curve, inpos, trades = backtest(df.time.values, df.open.values, df.high.values, df.low.values, df.close.values, P["f"]["atr"].fillna(0).values, sp, decide, lo, hi, cfg)
    return P, curve, inpos, trades, metrics(curve, inpos, trades, df.close.values[lo], df.close.values[hi - 1], cfg)

def replay(S, df, period, offset, n_bars, cfg):
    lo, hi, oos, lo0, hi0 = window(S, df, period, offset, n_bars); rec = {}
    sp = df.spread.values / 10.0; P, curve, inpos, trades, m = run_window(S, df, lo, hi, cfg, sp, rec)
    bars = [dict(time=int(df.time[i]), open=float(df.open[i]), high=float(df.high[i]), low=float(df.low[i]), close=float(df.close[i]), **rec.get(i, dict(regime=REG[int(P["g"][i])], decision="-", confidence=0, agents={}))) for i in range(lo, hi)]
    return dict(bars=bars, equity=[float(x) for x in curve], trades=trades, metrics=m, out_of_sample=oos, period=period, period_bars=hi0 - lo0, offset=lo - lo0, start=bars[0]["time"], end=bars[-1]["time"],
                note="Decision at each bar uses only data up to that bar's close; orders fill at the next open.")

def transform(df, lo, hi, vol_mult=1.0, gap=0.0, gap_at=0.5, rev_at=None):
    """Rebuild OHLC for bars [lo,hi) after a what-if shock. Everything is expressed as log offsets from the previous close."""
    c = df.close.values.astype(float); pc = np.r_[c[lo - 1], c[lo:hi - 1]]
    r = {k: np.log(df[k].values[lo:hi].astype(float) / pc) for k in ("open", "high", "low", "close")}
    if rev_at is not None:                                    # trend reversal: mirror returns after the chosen point
        k = int(rev_at * (hi - lo)); o, h, l, cl = (r[x][k:].copy() for x in ("open", "high", "low", "close"))
        r["open"][k:], r["close"][k:], r["high"][k:], r["low"][k:] = -o, -cl, -l, -h
    for x in r: r[x] = r[x] * vol_mult
    if gap:
        g = min(hi - lo - 1, int(gap_at * (hi - lo)))
        for x in r: r[x][g] += np.log(1 + gap)
    npc = c[lo - 1] * np.exp(np.r_[0.0, np.cumsum(r["close"])[:-1]]); d = df.copy()
    for x in r: d.loc[d.index[lo:hi], x] = npc * np.exp(r[x])
    return d

def scenario(S, df, period, offset, n_bars, cfg, p):
    from dataclasses import replace
    lo, hi, oos, *_ = window(S, df, period, offset, n_bars); sp = df.spread.values / 10.0
    d2 = transform(df, lo, hi, p["vol_mult"], p["gap_pct"] / 100, p["gap_at_pct"] / 100, None if p["reversal_at_pct"] is None else p["reversal_at_pct"] / 100)
    cfg2 = replace(cfg, slippage_pips=cfg.slippage_pips + p["extra_slippage_pips"]); sp2 = np.where(sp > 0, sp, cfg.default_spread_pips) * p["spread_mult"]
    out = {}
    for name, dd, c, s in (("baseline", df, cfg, sp), ("scenario", d2, cfg2, sp2)):
        P, curve, inpos, trades, m = run_window(S, dd, lo, hi, c, s); k = max(1, len(curve) // 400)
        out[name] = dict(metrics=m, curve=[float(x) for x in curve[::k]], high_vol_share=float((P["vo"][lo:hi] == 2).mean()), trades_n=len(trades))
    return dict(**out, out_of_sample=oos, bars=hi - lo, start=int(df.time[lo]), end=int(df.time[hi - 1]), params=p)
