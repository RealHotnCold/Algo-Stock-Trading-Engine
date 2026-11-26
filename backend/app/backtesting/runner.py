import time, numpy as np
from .engine import backtest, metrics

def run(S, df, period, cfg, spread_pips=None):
    """Backtest strategy S on bar DataFrame df over 'test' | 'val' | 'all'."""
    n = len(df); P = S.prep(df); matches = n == S.split["test"][1] + 1     # same data as training -> splits exact
    lo, hi = (S.split["train"][0], n - 1) if period == "all" else S.split[period] if matches else (int(n * (0.8 if period == "test" else 0.6)), n - 1 if period == "test" else int(n * 0.8))
    sp = df.spread.values / 10.0                                            # points -> pips (5-digit broker)
    if spread_pips: sp = np.full(n, spread_pips)
    mlo = max(0, lo - S.M); t0 = time.perf_counter()
    curve, inpos, trades = backtest(df.time.values, df.open.values, df.high.values, df.low.values, df.close.values, P["f"]["atr"].fillna(0).values, sp,
                                    lambda i, pos: S.step(P, i, pos, lo=mlo)["target"], lo, hi, cfg)
    m = metrics(curve, inpos, trades, df.close.values[lo], df.close.values[hi - 1], cfg); k = max(1, len(curve) // 1500)
    cov = 100 * (df.spread.values[lo:hi] > 0).mean()
    return {"metrics": m, "out_of_sample": bool(matches and period == "test"), "period": period, "start": int(df.time[lo]), "end": int(df.time[hi - 1]), "bars": hi - lo,
            "spread_source": "user constant" if spread_pips else f"stored bar spread on {cov:.0f}% of bars; 1.0 pip default elsewhere",
            "assumptions": "fills at next bar open; half-spread + slippage per fill; SL assumed first when ambiguous; zero commission; USD-quote account",
            "curve": [{"time": int(df.time[lo + j]), "equity": float(curve[j])} for j in range(0, len(curve), k)], "trades": trades[-500:], "n_trades_total": len(trades),
            "runtime_s": round(time.perf_counter() - t0, 1)}
