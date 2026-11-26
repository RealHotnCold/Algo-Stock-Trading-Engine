import numpy as np, pandas as pd
from app.simulations import blackscholes as bsm, monte_carlo as mc, replay as rp

def test_bs_reference_values_and_parity():
    c = bsm.bs(100, 100, 1, 0.05, 0.2, "call"); p = bsm.bs(100, 100, 1, 0.05, 0.2, "put")
    assert abs(float(c["price"]) - 10.4506) < 1e-3 and abs(float(p["price"]) - 5.5735) < 1e-3
    assert abs(float(c["price"] - p["price"]) - (100 - 100 * np.exp(-0.05))) < 1e-9          # put-call parity
    assert abs(float(c["delta"]) - 0.6368) < 1e-3 and float(c["gamma"]) > 0 and float(c["vega"]) > 0

def test_bs_greeks_match_finite_differences():
    f = lambda **k: float(bsm.bs(**{**dict(S=100, K=105, T=0.5, r=0.03, sigma=0.25, kind="put", q=0.01), **k})["price"]); g = bsm.bs(100, 105, 0.5, 0.03, 0.25, "put", 0.01)
    assert abs(float(g["delta"]) - (f(S=100.01) - f(S=99.99)) / 0.02) < 1e-4
    assert abs(float(g["gamma"]) - (f(S=100.1) - 2 * f() + f(S=99.9)) / 0.01) < 1e-4
    assert abs(float(g["vega"]) - (f(sigma=0.2501) - f(sigma=0.2499)) / 0.0002 / 100) < 1e-4
    assert abs(float(g["theta"]) - (f(T=0.5 - 1 / 365) - f()) ) < 5e-3

def test_mc_deterministic_and_ordered():
    close = 1.1 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 3e-4, 3000)))
    a, _ = mc.price_paths(close, "bootstrap", 200, 100, "zero", 12, np.random.default_rng(1)); b, _ = mc.price_paths(close, "bootstrap", 200, 100, "zero", 12, np.random.default_rng(1))
    assert np.array_equal(a, b) and a.shape == (200, 101) and np.allclose(a[:, 0], close[-1])
    s = mc.summarize(mc.portfolio(a, 10000, 1, 10), 10000, 0.5, np.random.default_rng(2)); m = s["metrics"]
    assert s["bands"]["p5"][-1] <= s["bands"]["p50"][-1] <= s["bands"]["p95"][-1] and m["cvar95_pct"] >= m["var95_pct"] and 0 <= m["prob_profit"] + m["prob_loss"] <= 1.0001

def test_mc_zero_vol_and_wipeout():
    flat = mc.portfolio(np.full((5, 11), 1.1), 1000, 1, 10); assert (flat == 1000).all()
    crash = np.tile(np.linspace(1.0, 0.5, 11), (3, 1)); e = mc.portfolio(crash, 1000, 1, 10); assert (e[:, -1] == 0).all()   # 10x long, -50% => wiped out, stays at 0

def test_scenario_transform():
    n = 60; c = 1.1 + np.arange(n) * 1e-4; df = pd.DataFrame(dict(time=np.arange(n) * 300, open=c - 5e-5, high=c + 1e-4, low=c - 1e-4, close=c, volume=1.0, spread=0.0))
    same = rp.transform(df, 20, 50); assert np.allclose(same[["open", "high", "low", "close"]].values, df[["open", "high", "low", "close"]].values)
    v = rp.transform(df, 20, 50, vol_mult=2.0); assert np.allclose(v.close.values[:20], c[:20]) and (v.high >= v[["open", "close"]].max(axis=1) - 1e-12).all()
    g = rp.transform(df, 20, 50, gap=0.01, gap_at=0.5); assert abs((g.open.values[35] / g.close.values[34]) / (df.open.values[35] / df.close.values[34]) - 1.01) < 1e-9     # gap adds +1% on top of the normal open
    r = rp.transform(df, 20, 50, rev_at=0.5); assert r.close.values[49] < r.close.values[35]                                  # drifting up -> mirrored down
