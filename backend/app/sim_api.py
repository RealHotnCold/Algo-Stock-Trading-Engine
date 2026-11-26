import time
import numpy as np, pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .market_data import history
from .backtesting.engine import BtConfig, BARS_PER_YEAR
from .simulations import monte_carlo as mc, blackscholes as bsm, replay as rp

router = APIRouter(prefix="/api/sim")
BARS_DAY = {"M5": 288, "M15": 96, "H1": 24}

def _df(symbol, tf, count=10**7):
    if tf not in BARS_PER_YEAR: raise HTTPException(400, f"timeframe must be one of {list(BARS_PER_YEAR)}")
    rows = history.load(symbol, tf, count)
    if len(rows) < 500: raise HTTPException(404, "not enough stored data; import a CSV first")
    return pd.DataFrame(rows)

def _model(tf):
    from .main import _model as m
    return m(tf)

@router.get("/hist-vol")
def hist_vol(symbol: str = "EURUSD", tf: str = "M5"):
    d = _df(symbol, tf, 20000); lr = np.diff(np.log(d.close.values))
    return {"last_close": float(d.close.values[-1]), "annual_vol": float(lr.std() * np.sqrt(BARS_PER_YEAR[tf])), "bars": len(d)}

class McIn(BaseModel):
    symbol: str = "EURUSD"; tf: str = "M5"; lookback_bars: int = 20000; method: str = "bootstrap"   # bootstrap | gbm | strategy_trades
    drift: str = "zero"; n_sims: int = 1000; horizon: int = 1000; capital: float = 10000; direction: int = 1; leverage: float = 10
    block: int = 24; ruin_level: float = 0.5; seed: int = 42

@router.post("/montecarlo")
def montecarlo(b: McIn):
    if b.method not in ("bootstrap", "gbm", "strategy_trades"): raise HTTPException(400, "bad method")
    if b.n_sims * b.horizon > mc.MAX_CELLS: raise HTTPException(400, f"n_sims x horizon must be <= {mc.MAX_CELLS:,}")
    if b.n_sims < 10 or b.horizon < 5 or b.direction not in (-1, 1): raise HTTPException(400, "invalid inputs")
    t0 = time.perf_counter(); rng = np.random.default_rng(b.seed); d = _df(b.symbol, b.tf, b.lookback_bars); info = {}
    if b.method == "strategy_trades":
        from .backtesting import runner
        r = runner.run(_model(b.tf), _df(b.symbol, b.tf), "test", BtConfig(initial_capital=b.capital, bars_yr=BARS_PER_YEAR[b.tf]))
        pnl = np.array([t["pnl"] for t in r["trades"]])
        if len(pnl) < 20: raise HTTPException(400, "too few trades to resample")
        eq = mc.trade_paths(pnl, b.n_sims, b.horizon, b.capital, rng); info = dict(source="out-of-sample test-period trades of the trained strategy", trades_used=len(pnl), unit="trades", note="resamples fixed-size trade P&L with replacement; no compounding")
    else:
        if len(d) < b.block * 3: raise HTTPException(400, "lookback too small for block size")
        paths, s = mc.price_paths(d.close.values, b.method, b.n_sims, b.horizon, b.drift, max(1, b.block), rng)
        eq = mc.portfolio(paths, b.capital, b.direction, b.leverage)
        info = dict(source=f"{len(d)} stored {b.tf} bars", unit="bars", per_bar_vol=s, annual_vol=float(s * np.sqrt(BARS_PER_YEAR[b.tf])), horizon_days=b.horizon / BARS_DAY[b.tf],
                    note=f"{b.method} with {b.drift} drift; {'long' if b.direction > 0 else 'short'} {b.leverage}x notional; positions wiped out at zero equity; no costs")
        info["example_price_p5_p95"] = [float(np.percentile(paths[:, -1], 5)), float(np.percentile(paths[:, -1], 95))]
    out = mc.summarize(eq, b.capital, b.ruin_level, rng)
    return {**out, "info": info, "synthetic": True, "limitations": "Synthetic paths from past returns; assumes the future resembles the sample (stable volatility, no regime change, no fat-tail events beyond those in the sample). Not a forecast.", "runtime_s": round(time.perf_counter() - t0, 2)}

class BsIn(BaseModel):
    S: float; K: float; days: float; sigma: float; r: float = 0.03; q: float = 0.0; kind: str = "call"   # sigma, r, q as decimals

@router.post("/blackscholes")
def blackscholes(b: BsIn):
    if min(b.S, b.K, b.days, b.sigma) <= 0 or b.kind not in ("call", "put"): raise HTTPException(400, "S, K, days, sigma must be > 0; kind call|put")
    T = b.days / 365; one = {k: float(v) for k, v in bsm.bs(b.S, b.K, T, b.r, b.sigma, b.kind, b.q).items()}
    sg = np.linspace(0.7 * b.S, 1.3 * b.S, 121); vg = np.linspace(max(0.01, b.sigma / 4), b.sigma * 2.5, 60); tg = np.linspace(b.days, 1, 60)
    now = bsm.bs(sg, b.K, T, b.r, b.sigma, b.kind, b.q); payoff = np.maximum(sg - b.K, 0) if b.kind == "call" else np.maximum(b.K - sg, 0)
    return {"theoretical": True, "greeks": one, "note": "Theoretical price from the parameters you entered; MT5 supplies no option quotes here. Greeks: vega per 1 vol point, theta per calendar day, rho per 1% rate.",
            "spot": {"x": sg.tolist(), "value": now["price"].tolist(), "payoff": payoff.tolist(), "delta": now["delta"].tolist(), "gamma": now["gamma"].tolist()},
            "vol": {"x": (vg * 100).tolist(), "value": bsm.bs(b.S, b.K, T, b.r, vg, b.kind, b.q)["price"].tolist()},
            "time": {"x": tg.tolist(), "value": bsm.bs(b.S, b.K, tg / 365, b.r, b.sigma, b.kind, b.q)["price"].tolist()}}

class WinIn(BaseModel):
    symbol: str = "EURUSD"; tf: str = "M5"; period: str = "test"; offset: int = 0; n_bars: int = 300
    initial_capital: float = 10000; risk_pct: float = 1.0; sl_atr: float = 2.0; tp_atr: float = 3.0; slippage_pips: float = 0.1; cooldown_bars: int = 0

def _cfg(b): return BtConfig(initial_capital=b.initial_capital, risk_pct=b.risk_pct, sl_atr=b.sl_atr, tp_atr=b.tp_atr, slippage_pips=b.slippage_pips, cooldown_bars=b.cooldown_bars, bars_yr=BARS_PER_YEAR[b.tf])

@router.post("/replay")
def replay(b: WinIn):
    if b.period not in ("test", "val", "all") or not 20 <= b.n_bars <= 1500: raise HTTPException(400, "period test|val|all; n_bars 20-1500")
    return rp.replay(_model(b.tf), _df(b.symbol, b.tf), b.period, b.offset, b.n_bars, _cfg(b))

class ScIn(WinIn):
    n_bars: int = 3000; vol_mult: float = 1.0; gap_pct: float = 0.0; gap_at_pct: float = 50; reversal_at_pct: float | None = None; spread_mult: float = 1.0; extra_slippage_pips: float = 0.0

@router.post("/scenario")
def scenario(b: ScIn):
    if b.period not in ("test", "val", "all") or not 100 <= b.n_bars <= 6000 or b.vol_mult <= 0 or b.spread_mult <= 0 or abs(b.gap_pct) >= 50: raise HTTPException(400, "invalid scenario inputs")
    t0 = time.perf_counter(); r = rp.scenario(_model(b.tf), _df(b.symbol, b.tf), b.period, b.offset, b.n_bars, _cfg(b), b.model_dump())
    return {**r, "runtime_s": round(time.perf_counter() - t0, 1), "note": "Shocks are applied to the chosen window only; trained scaler/regime thresholds are unchanged, so regimes shift under the scenario."}
