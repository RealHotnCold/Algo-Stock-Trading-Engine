"""Walk-forward evaluation. Each fold retrains EVERYTHING (agents, scaler, regimes, gating, threshold) on a rolling window and is scored on the
window's final 20% (never seen in any fitting step). Test windows of consecutive folds are contiguous, so they stitch into one out-of-sample record."""
import math
import numpy as np
from .backtesting.engine import BtConfig, BARS_PER_YEAR, backtest
from .market_data.history import parse_csv, resample
from .simulations.replay import run_window, bounds
from .strategy.meta import Strategy

CONFIGS = [("M5", False, 0), ("M5", True, 12), ("M15", False, 0), ("M15", True, 4), ("H1", False, 0), ("H1", True, 1)]   # tf, drift_neutral, SL cooldown bars (~1h)
N_NULL = 20

def folds_for(n, frac=0.5):
    W = int(n * frac); step = int(0.2 * (W - 96)); return W, list(range(0, n - W + 1, step))

def sign_p(k, n): return sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n      # P(>= k positive folds out of n if each were a coin flip)

def boot_ci(x, n=2000, seed=0):
    x = np.asarray(x, float); rng = np.random.default_rng(seed); m = rng.choice(x, (n, len(x))).mean(1); return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]

def stitch(rets, cap=10000.0, bars_yr=72576, pts=300):
    r = np.concatenate(rets); eq = cap * np.cumprod(1 + r); pk = np.maximum.accumulate(eq)
    idx = np.linspace(0, len(eq) - 1, pts).astype(int)
    return dict(total_return_pct=float(100 * (eq[-1] / cap - 1)), max_dd_pct=float(100 * ((pk - eq) / pk).max()), sharpe=float(r.mean() / (r.std() + 1e-12) * np.sqrt(bars_yr)), bars=int(len(r))), [float(eq[i]) for i in idx]

def run_config(csv, idx, steps=3000):
    tf, dn, cd = CONFIGS[idx]; df5 = parse_csv(open(csv, "rb").read()).reset_index(drop=True); df = df5 if tf == "M5" else resample(df5, tf)
    W, starts = folds_for(len(df)); cfg = BtConfig(cooldown_bars=cd, bars_yr=BARS_PER_YEAR[tf]); folds, rets, pnls = [], [], []
    for k, s0 in enumerate(starts):
        try:
            d = df.iloc[s0:s0 + W].reset_index(drop=True); S = Strategy(); S.fit(d, steps=steps, drift_neutral=dn, log=lambda *a: None)
            lo, hi, oos, *_ = bounds(S, len(d), "test"); sp = d.spread.values / 10.0
            P, curve, inpos, trades, m = run_window(S, d, lo, hi, cfg, sp)
            rets.append(np.diff(curve) / curve[:-1]); pnls += [t["pnl"] for t in trades]
            p = min(0.5, max(2 * len(trades) / (hi - lo), 1e-4)); atr = P["f"]["atr"].fillna(0).values; nulls = []      # random-entry null with ~matched trade frequency, same costs/SL/TP
            for seed in range(N_NULL):
                rng = np.random.default_rng(1000 * k + seed)
                c2 = backtest(d.time.values, d.open.values, d.high.values, d.low.values, d.close.values, atr, sp, lambda i, pos, rng=rng: int(rng.choice((-1, 1))) if rng.random() < p else pos, lo, hi, cfg)[0]
                nulls.append(100 * (c2[-1] / cfg.initial_capital - 1))
            nulls = np.array(nulls)
            folds.append(dict(fold=k, start=int(d.time[lo]), end=int(d.time[hi - 1]), bars=hi - lo, return_pct=m["total_return_pct"], profit_factor=m["profit_factor"], trades=m["trades"],
                              max_dd_pct=m["max_drawdown_pct"], sharpe=m["sharpe"], buy_hold_pct=m["benchmark_buy_hold_pct"], exposure_pct=m["exposure_pct"], null_mean_pct=float(nulls.mean()),
                              null_p5_pct=float(np.percentile(nulls, 5)), null_p95_pct=float(np.percentile(nulls, 95)), null_rank_pct=float((nulls < m["total_return_pct"]).mean() * 100)))
        except Exception as e:                                                   # report failed folds instead of hiding them
            folds.append(dict(fold=k, error=f"{type(e).__name__}: {e}"))
    ok = [f for f in folds if "error" not in f]
    if not ok: return dict(tf=tf, drift_neutral=dn, cooldown_bars=cd, folds=folds, error="all folds failed")
    st, curve = stitch(rets, bars_yr=BARS_PER_YEAR[tf]); r = [f["return_pct"] for f in ok]; pos = sum(x > 0 for x in r)
    pn = np.array(pnls) if pnls else np.array([0.0])
    return dict(tf=tf, drift_neutral=dn, cooldown_bars=cd, n_folds=len(ok), folds=folds, stitched=st, curve=curve, buy_hold_stitched_pct=float(100 * (np.prod([1 + f["buy_hold_pct"] / 100 for f in ok]) - 1)),
                folds_positive=int(pos), sign_test_p=sign_p(pos, len(ok)), mean_fold_return_pct=float(np.mean(r)), median_fold_return_pct=float(np.median(r)),
                mean_excess_vs_random_pct=float(np.mean([f["return_pct"] - f["null_mean_pct"] for f in ok])),
                pooled_trades=dict(n=int(len(pnls)), mean_pnl=float(pn.mean()), ci95=boot_ci(pn), t_stat=float(pn.mean() / (pn.std(ddof=1) / np.sqrt(len(pn)) + 1e-12)) if len(pn) > 2 else None))
