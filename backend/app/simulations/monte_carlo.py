"""Monte Carlo: simulated (synthetic) price/portfolio paths from historical returns. Not forecasts."""
import numpy as np
MAX_CELLS = 5_000_000

def _hist(a, bins=40):
    c, e = np.histogram(a, bins=bins); return {"counts": c.tolist(), "edges": [float(x) for x in e]}

def price_paths(close, method, n, H, drift, block, rng):
    lr = np.diff(np.log(close)); s = float(lr.std())
    if method == "gbm":
        m = float(lr.mean()) if drift == "historical" else -0.5 * s * s
        inc = rng.normal(m, s, (n, H))
    else:                                                   # block bootstrap keeps short-range dependence/vol clustering
        base = lr if drift == "historical" else lr - lr.mean() - 0.5 * s * s
        nb = -(-H // block); st = rng.integers(0, len(base) - block + 1, (n, nb))
        inc = base[st[:, :, None] + np.arange(block)].reshape(n, -1)[:, :H]
    return close[-1] * np.exp(np.concatenate([np.zeros((n, 1)), np.cumsum(inc, 1)], 1)), s

def portfolio(paths, capital, direction, leverage):
    eq = capital * (1 + direction * leverage * (paths / paths[:, :1] - 1)); eq = np.maximum(eq, 0)
    eq[np.cumsum(eq <= 0, 1) > 0] = 0; return eq             # wipe-out is absorbing

def trade_paths(pnl, n, H, capital, rng):
    eq = capital + np.concatenate([np.zeros((n, 1)), np.cumsum(pnl[rng.integers(0, len(pnl), (n, H))], 1)], 1)
    eq = np.maximum(eq, 0); eq[np.cumsum(eq <= 0, 1) > 0] = 0; return eq

def summarize(eq, capital, ruin_level, rng, keep=30):
    fin = eq[:, -1]; ret = fin / capital - 1; p5 = np.percentile(ret, 5)
    peak = np.maximum.accumulate(eq, 1); dd = ((peak - eq) / np.maximum(peak, 1e-9)).max(1)
    idx = np.unique(np.linspace(0, eq.shape[1] - 1, min(200, eq.shape[1])).astype(int)); q = np.percentile(eq[:, idx], [5, 25, 50, 75, 95], axis=0)
    pick = rng.choice(len(eq), min(keep, len(eq)), replace=False)
    return {"metrics": dict(expected_final=float(fin.mean()), median_final=float(np.median(fin)), p5_final=float(np.percentile(fin, 5)), p95_final=float(np.percentile(fin, 95)),
                            prob_profit=float((fin > capital).mean()), prob_loss=float((fin < capital).mean()), var95_pct=float(-p5 * 100), cvar95_pct=float(-ret[ret <= p5].mean() * 100),
                            median_max_dd_pct=float(np.median(dd) * 100), p95_max_dd_pct=float(np.percentile(dd, 95) * 100),
                            risk_of_ruin=float((eq.min(1) <= ruin_level * capital).mean())),
            "x": idx.tolist(), "bands": {k: q[i].tolist() for i, k in enumerate(("p5", "p25", "p50", "p75", "p95"))},
            "sample_paths": [eq[j, idx].tolist() for j in pick], "hist_final_return_pct": _hist(ret * 100), "hist_max_dd_pct": _hist(dd * 100)}
