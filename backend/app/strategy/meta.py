"""Regime-gated, memory-augmented meta-decision over 4 DDQN agents (MacroHFT-inspired adaptation, not a reproduction)."""
import numpy as np
from ..agents import dqn
from . import features
from .features import FEATS, Scaler
from .regime import RegimeModel, NAMES as REG
COST_BPS = 0.55   # ASSUMPTION: ~0.6 pip half-spread+slippage per unit position change at EURUSD~1.15; replace with real spreads in backtester
AGENTS = {  # name: (feature columns, training-slice rule on (trend_state, vol_state))
    "trend":      (["trend_t", "ema_diff", "ret_36", "ret_12"],      lambda tr, vo: tr != 1),
    "momentum":   (["ret_1", "ret_6", "ret_12", "rsi", "ret_accel"], lambda tr, vo: vo >= 1),
    "volatility": (["rv_ratio", "rv_48", "atr", "vol_chg", "ret_1"], lambda tr, vo: vo == 2),
    "meanrev":    (["zscore", "rsi", "ret_6", "ema_diff"],           lambda tr, vo: tr == 1)}
ACT = {0: "sell", 1: "flat", 2: "buy"}
NAMES = list(AGENTS)
def _adv(q): return q - q.mean()
def _sm(x): e = np.exp(x - x.max()); return e / e.sum()

class Strategy:
    M, K, BETA, MIN_N = 2000, 20, 1.0, 150
    def prep(self, df):
        df = df.reset_index(drop=True); f = features.compute(df); valid = ~np.isnan(f.values).any(1)
        Z = np.where(valid[:, None], self.sc.transform(f.fillna(0)), 0.0)
        g, tr, vo = self.reg.label(f.fillna(0)); g = np.where(valid, g, 0)
        c = df.close.values; r = np.r_[(c[1:] / c[:-1] - 1) * 1e4, np.nan]
        oh = np.eye(9)[g]; ix = {n: [FEATS.index(k) for k in AGENTS[n][0]] for n in NAMES}
        B = {n: np.c_[Z[:, ix[n]], oh] for n in NAMES}
        G = np.full((len(df), 4), np.nan)
        for i, n in enumerate(NAMES):   # memory outcome: gross reward of each agent's greedy flat-state action
            a = self.nets[n].q(np.c_[B[n], np.zeros(len(df))]).argmax(1) - 1; G[:, i] = a * (r - getattr(self, "mu_r", 0.0))
        return dict(f=f, Z=Z, g=g, tr=tr, vo=vo, r=r, B=B, G=G, valid=valid, ts=df.time.values)

    def fit(self, df, steps=3000, log=print, drift_neutral=False):
        df = df.reset_index(drop=True); f = features.compute(df); ok = np.where(~np.isnan(f.values).any(1))[0]
        n = len(ok); a, b = ok[0], ok[0] + int(n * .6); c2 = ok[0] + int(n * .8); N = len(df)
        self.split = dict(train=(int(a), int(b)), val=(int(b), int(c2)), test=(int(c2), N - 1))
        self.sc = Scaler().fit(f.iloc[a:b]); self.reg = RegimeModel().fit(f.iloc[a:b])
        self.nets = {}; P0 = None
        tmp = Strategy(); tmp.sc, tmp.reg, tmp.nets = self.sc, self.reg, {n: dqn.MLP([1, 1]) for n in NAMES}
        Z = self.sc.transform(f.fillna(0)); g, tr, vo = self.reg.label(f.fillna(0)); oh = np.eye(9)[g]
        c = df.close.values; r = np.r_[(c[1:] / c[:-1] - 1) * 1e4, np.nan]
        self.mu_r = float(np.nanmean(r[a:b])) if drift_neutral else 0.0   # drift-neutral: reward = position * (return - train mean)
        r = r - self.mu_r
        for nme in NAMES:
            cols, rule = AGENTS[nme]; B = np.c_[Z[:, [FEATS.index(k) for k in cols]], oh]
            idx = np.array([t for t in range(a, b - 1) if rule(tr[t], vo[t])])
            net, hist = dqn.train(B, r, idx, COST_BPS, self.split["val"], steps=steps, seed=1)
            self.nets[nme] = net; log(f"agent {nme:10s} slice={len(idx):6d} val mean bps/bar by checkpoint={np.round(hist, 3).tolist()}")
        P = self.prep(df); self.P_cache = None
        lo, hi = self.split["val"]; self.gs = float(np.nanstd(P["G"][a:b]))
        sims = [dqn.simulate(self.nets[n], P["B"][n], P["r"] - self.mu_r, lo, hi, COST_BPS)[0] for n in NAMES]
        self.W = np.zeros((9, 4)); gv = P["g"][lo:hi]
        for gi in range(9):
            sc = np.zeros(4)
            for i in range(4):
                x = sims[i][gv == gi]
                if len(x) >= self.MIN_N and x.mean() > 0: sc[i] = x.mean() / (x.std() + 1e-9)
            if sc.sum() > 0: self.W[gi] = sc / sc.sum()
        log("gating weights (rows=regime; zero row = abstain):")
        for gi in range(9): log(f"  {REG[gi]:14s} {np.round(self.W[gi], 2).tolist()}")
        A0 = [np.array([_adv(self.nets[n].q(np.append(P["B"][n][t], 0)[None])[0]) for n in NAMES]).mean(0) for t in range(lo, hi, 10)]
        self.T = float(np.std(A0)) + 1e-9; self.thr = 0.4
        best = (-1e9, .4)
        for th in (.35, .4, .45, .5):
            self.thr = th; s = self.run(P, lo, hi)[0].mean()
            if s > best[0]: best = (s, th)
        self.thr = best[1]; log(f"selected confidence threshold on validation: {self.thr}")
        return P

    def step(self, P, t, pos, lo=0):
        A = np.array([_adv(self.nets[n].q(np.append(P["B"][n][t], pos)[None])[0]) for n in NAMES]); gi = P["g"][t]
        w0 = self.W[gi].copy(); w = w0.copy(); mem = np.zeros(4); nmem = 0
        if w.sum() > 0:
            idx = np.arange(max(lo, t - self.M), t); idx = idx[P["valid"][idx] & ~np.isnan(P["G"][idx, 0])]
            if len(idx) >= self.K:
                d = ((P["Z"][idx] - P["Z"][t]) ** 2).sum(1); nn = idx[np.argpartition(d, self.K - 1)[:self.K]]
                mem = P["G"][nn].mean(0); nmem = self.K; w = w * np.exp(self.BETA * np.tanh(mem / self.gs))
        if w.sum() <= 0: return dict(target=0, label="No trade", conf=0.0, reason="regime abstain", A=A, w0=w0, w=w, mem=mem, nmem=nmem, regime=gi, p=None)
        w = w / w.sum(); Qm = (w[:, None] * A).sum(0); p = _sm(Qm / self.T); a = int(Qm.argmax()); conf = float(p[a])
        target = a - 1 if conf >= self.thr else 0
        label = "No trade" if conf < self.thr else ("Buy" if target > pos else "Sell" if target < pos else "Hold")
        if conf >= self.thr and target == 0: label = "Hold" if pos == 0 else "Sell" if pos > 0 else "Buy"
        return dict(target=target, label=label, conf=conf, reason="low confidence" if conf < self.thr else "", A=A, w0=w0, w=w, mem=mem, nmem=nmem, regime=gi, p=p)

    def run(self, P, lo, hi, demean=True):
        mu = getattr(self, "mu_r", 0.0) if demean else 0.0
        pos, out, ps = 0, np.zeros(hi - lo), np.zeros(hi - lo)
        for i, t in enumerate(range(lo, hi)):
            d = self.step(P, t, pos, lo=lo - self.M if lo - self.M > 0 else 0); np_ = d["target"]
            out[i] = np_ * (P["r"][t] - mu) - COST_BPS * abs(np_ - pos); ps[i] = np_; pos = np_
        return out, ps

    def explain(self, df, pos=0):
        P = self.prep(df); t = len(df) - 1; d = self.step(P, t, pos); f = P["f"].iloc[t]; agents = []
        for i, n in enumerate(NAMES):
            adv = d["A"][i]; a = int(adv.argmax()); marg = float(np.sort(adv)[-1] - np.sort(adv)[-2])
            vals = ", ".join(f"{k}={f[k]:+.2f}" for k in AGENTS[n][0])
            agents.append(dict(agent=n, action=ACT[a], confidence=float(_sm(adv / self.T)[a]), base_weight=float(d["w0"][i]),
                               memory_outcome_bps=float(d["mem"][i]), final_weight=float(d["w"][i]) if d["w"].sum() <= 1.0001 else None,
                               rationale=f"inputs [{vals}] in regime {REG[d['regime']]}; learned policy prefers {ACT[a]} (advantage margin {marg:.2f})"))
        return dict(regime=REG[d["regime"]], decision=d["label"], target_position=d["target"], confidence=d["conf"], threshold=self.thr,
                    abstain_reason=d["reason"], memory_neighbors=d["nmem"], agents=agents,
                    note="MacroHFT-inspired adaptation; offline-trained NumPy DDQN agents; not an exact reproduction.")

def metrics(x, pos=None):
    bars_yr = 252 * 288; cs = np.cumsum(x)
    return dict(total_bps=round(float(x.sum()), 1), sharpe=round(float(x.mean() / (x.std() + 1e-12) * np.sqrt(bars_yr)), 2),
                max_dd_bps=round(float((np.maximum.accumulate(cs) - cs).max()), 1),
                trades=int((np.abs(np.diff(np.r_[0, pos])) > 0).sum()) if pos is not None else None,
                exposure=round(float((pos != 0).mean()), 3) if pos is not None else None)
