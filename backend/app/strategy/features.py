"""Causal features: row t uses only bars <= t. Returns in bps."""
import numpy as np, pandas as pd
FEATS = ["ret_1", "ret_6", "ret_12", "ret_36", "rv_48", "rv_ratio", "trend_t", "ema_diff", "atr", "zscore", "rsi", "vol_chg", "ret_accel"]

def compute(df: pd.DataFrame) -> pd.DataFrame:
    c, lc = df.close.reset_index(drop=True), np.log(df.close.reset_index(drop=True))
    h, l, v = df.high.reset_index(drop=True), df.low.reset_index(drop=True), df.volume.reset_index(drop=True)
    lr = lc.diff(); f = pd.DataFrame(index=c.index)
    f["ret_1"] = lr * 1e4
    for n in (6, 12, 36): f[f"ret_{n}"] = lc.diff(n) * 1e4
    f["rv_48"] = lr.rolling(48).std() * 1e4
    f["rv_ratio"] = np.log(lr.rolling(12).std() / lr.rolling(96).std())
    r = lc.rolling(48).corr(pd.Series(np.arange(len(c), dtype=float)))       # slope t-stat via corr with time
    f["trend_t"] = r * np.sqrt(46 / (1 - r ** 2 + 1e-12))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1); atr = tr.rolling(14).mean()
    f["atr"] = atr / c * 1e4
    f["ema_diff"] = (c.ewm(span=12, adjust=False).mean() - c.ewm(span=48, adjust=False).mean()) / atr
    f["zscore"] = (c - c.rolling(48).mean()) / c.rolling(48).std()
    d = c.diff(); up, dn = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    f["rsi"] = (100 - 100 / (1 + up / (dn + 1e-12)) - 50) / 50
    f["vol_chg"] = np.log((v + 1) / (v.rolling(48).mean() + 1))
    f["ret_accel"] = f["ret_6"] - f["ret_6"].shift(6)
    f = f[FEATS].replace([np.inf, -np.inf], np.nan); f.index = df.index
    return f

class Scaler:  # fit on TRAIN only: winsorize 0.5/99.5 pct then z-score
    def fit(self, f):
        self.lo, self.hi = f.quantile(.005).values, f.quantile(.995).values
        x = f.clip(self.lo, self.hi, axis=1); self.mu, self.sd = x.mean().values, x.std().values + 1e-9; return self
    def transform(self, f): return (np.clip(f.values, self.lo, self.hi) - self.mu) / self.sd
