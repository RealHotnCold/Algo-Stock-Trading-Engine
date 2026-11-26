import asyncio
from fastapi import FastAPI, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .db import init_db
from .mt5.gateway import MT5Gateway, MT5Unavailable, TF_NAMES
from .market_data import history
from .execution.service import ExecutionService
from .risk.engine import RiskConfig, size_by_risk
from pydantic import BaseModel
import os, pickle, time
import pandas as pd

app = FastAPI(title="MacroHFT-inspired trading terminal")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
gw = MT5Gateway()
from .sim_api import router as sim_router
app.include_router(sim_router)
from .portfolio_api import router as pf_router
app.include_router(pf_router)
exe = ExecutionService(gw)

class OrderIn(BaseModel):
    symbol: str; side: str; volume: float; order_type: str = 'market'
    price: float | None = None; sl: float | None = None; tp: float | None = None; comment: str = 'terminal'

class SizeIn(BaseModel):
    symbol: str; side: str; sl: float

@app.on_event("startup")
def _startup():
    init_db()
    from . import settings_store
    saved = settings_store.load_risk()
    if saved: exe.cfg = saved            # restore persisted risk limits

@app.get("/api/status")
def status(): return gw.status()

@app.get("/api/timeframes")
def timeframes(): return TF_NAMES

@app.get("/api/symbols")
def symbols():
    try: return {"source": "mt5", "symbols": gw.symbols()}
    except MT5Unavailable:
        return {"source": "stored", "symbols": [{"name": n} for n in sorted({d["symbol"] for d in history.available()})]}

@app.get("/api/bars")
def bars(symbol: str, tf: str = "M5", count: int = 1000):
    if tf not in TF_NAMES: raise HTTPException(400, f"timeframe must be one of {TF_NAMES}")
    try: return {"source": "mt5", "bars": gw.bars(symbol, tf, count)}
    except MT5Unavailable:
        b = history.load(symbol, tf, count)
        if not b: raise HTTPException(404, "MT5 disconnected and no stored data for this symbol/timeframe")
        return {"source": "stored", "bars": b}

@app.get("/api/tick")
def tick(symbol: str):
    try: return gw.tick(symbol)
    except MT5Unavailable as e: raise HTTPException(503, f"MT5 disconnected: {e}")

@app.get("/api/data")
def data_inventory(): return history.available()

@app.post("/api/data/import")
async def data_import(symbol: str, tf: str, file: UploadFile):
    try: return {"imported": history.store(symbol, tf, history.parse_csv(await file.read()))}
    except (ValueError, KeyError) as e: raise HTTPException(400, str(e))

@app.websocket("/ws/ticks")
async def ws_ticks(ws: WebSocket, symbol: str):
    await ws.accept()
    try:
        while True:
            try: await ws.send_json({"ok": True, **await asyncio.to_thread(gw.tick, symbol)})
            except MT5Unavailable as e: await ws.send_json({"ok": False, "reason": str(e)})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect: pass

@app.get("/api/risk/config")
def risk_get(): return exe.cfg.__dict__

@app.put("/api/risk/config")
def risk_put(c: dict):
    from . import settings_store
    try: new = RiskConfig(**{**exe.cfg.__dict__, **settings_store.clean_risk(c)})
    except ValueError as e: raise HTTPException(400, str(e))
    exe.cfg = new; settings_store.save_risk(new); return exe.cfg.__dict__

@app.get("/api/settings")
def settings_get():
    from . import settings_store
    return settings_store.load()

@app.put("/api/settings")
def settings_put(p: dict):
    from . import settings_store
    try: return settings_store.update(p)
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/api/drawings")
def drawings_get(symbol: str, tf: str):
    from . import settings_store
    try: return {"items": settings_store.load_drawings(symbol, tf)}
    except ValueError as e: raise HTTPException(400, str(e))

@app.put("/api/drawings")
def drawings_put(symbol: str, tf: str, body: dict):
    from . import settings_store
    try: return {"items": settings_store.save_drawings(symbol, tf, body.get("items"))}
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/api/mt5/reconnect")
def mt5_reconnect():
    try: gw.connect()
    except MT5Unavailable: pass
    return gw.status()

@app.post("/api/orders/size")
def order_size(b: SizeIn):
    try:
        spec, t, acc = gw.spec(b.symbol), gw.tick(b.symbol), gw.status()["account"]
        entry = t["ask"] if b.side == "buy" else t["bid"]
        return {"volume": size_by_risk(acc["equity"], exe.cfg.risk_per_trade_pct, entry, b.sl, spec), "entry": entry}
    except MT5Unavailable as e: raise HTTPException(503, f"MT5 unavailable: {e}")
    except Exception as e: raise HTTPException(500, f"{type(e).__name__}: {e}")

@app.post("/api/orders/validate")
def order_validate(o: OrderIn): return exe.validate(o.model_dump())

@app.post("/api/orders")
def order_submit(o: OrderIn): return exe.submit(o.model_dump(), source="manual")

@app.get("/api/positions")
def positions():
    try: return gw.positions()
    except MT5Unavailable as e: raise HTTPException(503, f"MT5 disconnected: {e}")

@app.post("/api/positions/{ticket}/close")
def close(ticket: int):
    try: r = gw.close_position(ticket)
    except MT5Unavailable as e: raise HTTPException(503, str(e))
    return {"closed": r["retcode"] in (10009,), "result": r}

_MODELS = {}
def _model(tf):
    if tf in _MODELS: return _MODELS[tf]
    for f in (f"models/strategy_{tf}_best.pkl", f"models/strategy_{tf}.pkl") + (("models/strategy.pkl",) if tf == "M5" else ()):
        if os.path.exists(f): _MODELS[tf] = pickle.load(open(f, "rb")); return _MODELS[tf]   # local trusted files only
    raise HTTPException(404, f"no trained model for {tf}; run: python train.py <csv> --tf {tf}")

@app.get("/api/strategy/signal")
def strategy_signal(symbol: str, tf: str = "M5"):
    """Decision on the last CLOSED bar, using the model trained for this timeframe."""
    S = _model(tf); r = bars(symbol, tf, 800); b = r["bars"][:-1] if r["source"] == "mt5" else r["bars"]   # drop forming bar
    if len(b) < 400: raise HTTPException(404, "need >=400 bars")
    pos = 0
    try:
        net = sum(p["volume"] * (1 if p["side"] == "buy" else -1) for p in gw.positions() if p["symbol"] == symbol); pos = (net > 0) - (net < 0)
    except MT5Unavailable: pass
    t0 = time.perf_counter(); e = S.explain(pd.DataFrame(b), pos=int(pos))
    return {**e, "data_source": r["source"], "bar_time": b[-1]["time"], "latency_infer_ms": (time.perf_counter() - t0) * 1000, "model_trained_on": f"EURUSD {tf}"}

def _json(path):
    import json
    if not os.path.exists(path): raise HTTPException(404, f"{path} missing; run train.py / compare.py")
    return json.load(open(path))

@app.get("/api/strategy/results")
def strategy_results(): return _json("models/results.json")

@app.get("/api/strategy/comparison")
def strategy_comparison(): return _json("models/comparison.json")

@app.get("/api/strategy/walkforward")
def strategy_walkforward(): return _json("models/walkforward.json")

class BtIn(BaseModel):
    symbol: str = "EURUSD"; tf: str = "M5"; period: str = "test"   # test | val | all
    initial_capital: float = 10000; risk_pct: float = 1.0; sl_atr: float = 2.0; tp_atr: float = 3.0
    spread_pips: float | None = None; slippage_pips: float = 0.1; cooldown_bars: int = 0

@app.post("/api/backtest")
def backtest_run(b: BtIn):
    from .backtesting import runner
    from .backtesting.engine import BtConfig, BARS_PER_YEAR
    if b.tf not in BARS_PER_YEAR: raise HTTPException(400, f"timeframe must be one of {list(BARS_PER_YEAR)}")
    S = _model(b.tf); rows = history.load(b.symbol, b.tf, 10**7)
    if len(rows) < 1000: raise HTTPException(404, "not enough stored data; import a CSV first")
    cfg = BtConfig(initial_capital=b.initial_capital, risk_pct=b.risk_pct, sl_atr=b.sl_atr, tp_atr=b.tp_atr, slippage_pips=b.slippage_pips,
                   cooldown_bars=b.cooldown_bars, bars_yr=BARS_PER_YEAR[b.tf])
    return {**runner.run(S, pd.DataFrame(rows), b.period, cfg, b.spread_pips), "tf": b.tf}

from .execution.autotrader import AutoTrader
auto = AutoTrader(gw, exe, lambda tf: _model(tf), lambda: __import__("app.settings_store", fromlist=["load"]).load()["strategy"])

class AutoIn(BaseModel):
    symbol: str = "EURUSD"; tf: str = "M5"; max_trades_per_day: int = 5

@app.post("/api/auto/start")
def auto_start(b: AutoIn):
    try: auto.start(b.symbol, b.tf, b.max_trades_per_day)
    except (ValueError, MT5Unavailable) as e: raise HTTPException(400, str(e))
    return auto.status()

@app.post("/api/auto/stop")
def auto_stop(close_positions: bool = False):
    try: return auto.stop(close_positions)
    except MT5Unavailable as e: raise HTTPException(503, str(e))

@app.post("/api/auto/preview")
def auto_preview(b: AutoIn):
    try: return auto.preview(b.symbol, b.tf)
    except (ValueError, MT5Unavailable) as e: raise HTTPException(400, str(e))
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f"{type(e).__name__}: {e}")

@app.get("/api/auto/status")
def auto_status(): return auto.status()
