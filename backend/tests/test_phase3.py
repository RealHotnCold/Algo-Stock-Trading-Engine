import numpy as np, pandas as pd
from app.strategy import features
from app.strategy.regime import RegimeModel
from app.agents import dqn

def _df(n=600, seed=0):
    r = np.random.default_rng(seed); c = 1.1 * np.exp(np.cumsum(r.normal(0, 3e-4, n)))
    return pd.DataFrame(dict(time=np.arange(n) * 300, open=c, high=c * 1.0002, low=c * 0.9998, close=c, volume=r.integers(50, 500, n).astype(float)))

def test_features_causal():
    d = _df(); d2 = d.copy(); d2.loc[400:, ["open", "high", "low", "close", "volume"]] *= 1.7
    a, b = features.compute(d).iloc[:400].fillna(0).values, features.compute(d2).iloc[:400].fillna(0).values
    assert np.allclose(a, b)

def test_regime_fit_on_train_only_and_grid():
    f = features.compute(_df()).dropna(); m = RegimeModel().fit(f.iloc[:200]); g, tr, vo = m.label(f)
    assert set(np.unique(g)) <= set(range(9)) and (g == tr * 3 + vo).all()
    assert np.allclose(m.vq, f.iloc[:200]["rv_48"].quantile([1 / 3, 2 / 3]).values)  # thresholds ignore later data

def test_dqn_learns_when_signal_exists():   # sanity of learning machinery: feature = next return (oracle) must be exploited
    rng = np.random.default_rng(0); r = rng.normal(0, 2, 3000); r[-1] = np.nan
    B = np.c_[r / 2, np.zeros(3000)]; idx = np.arange(0, 2000)
    net, _ = dqn.train(B, r, idx, 0.1, (2000, 2900), steps=1500, hidden=16, eval_every=500)
    assert dqn.simulate(net, B, r, 2000, 2900, 0.1)[0].mean() > 0.5
