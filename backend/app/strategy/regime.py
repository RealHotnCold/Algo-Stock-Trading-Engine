"""Trend x volatility regime grid (MacroHFT-style decomposition).
Trend: |t-stat of 48-bar log-price slope| > 2 (~5% significance). Volatility: terciles of rv_48 fitted on TRAIN only."""
import numpy as np
from .features import FEATS
TREND = ["down", "sideways", "up"]; VOL = ["low", "mid", "high"]
NAMES = [f"{t}/{v}" for t in TREND for v in VOL]

class RegimeModel:
    t_thr = 2.0
    def fit(self, f): self.vq = f["rv_48"].quantile([1 / 3, 2 / 3]).values; return self
    def label(self, f):
        t = f["trend_t"].values; rv = f["rv_48"].values
        tr = np.where(t > self.t_thr, 2, np.where(t < -self.t_thr, 0, 1))
        vo = np.digitize(rv, self.vq)
        return (tr * 3 + vo).astype(int), tr, vo
