# MacroHFT-inspired trading terminal (Phase 1)

## Run (Windows, for live MT5)
1. Install MetaTrader 5, log into a **demo** account in the terminal, enable Algo Trading.
2. Backend: `cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt && copy .env.example .env && uvicorn app.main:app --reload`
3. Frontend: `cd frontend && npm install && npm run dev` → http://localhost:5173
4. No MT5? App shows "disconnected" and serves only imported history: `POST /api/data/import?symbol=EURUSD&tf=M5` with an MT5-exported CSV (File → Open Data Folder, or History Center export).

Tests: `cd backend && pytest`
Safety: `DEMO_ONLY=true` and `ALLOW_REAL_TRADING=false` by default; real accounts stay blocked unless both are changed.

## Phases 2-3 + UI
- Train: `cd backend && python train.py <EURUSD_M5.csv> 3000` (writes models/strategy.pkl, results.json). Needs numpy/pandas only.
- Terminal: order panel (validate → confirm → execute), open positions with close, live research signal. Orders are blocked unless MT5 is connected to a demo account.
- Research tab: methodology, adaptations, test results, live decision. Signals are advisory; nothing auto-trades.

## Phase 4: backtesting
Re-import your CSV once (spreads are now stored): the Backtesting tab uses real bar spreads where the broker reported them (>0) and a 1-pip default elsewhere. Only the "Test" period is out-of-sample.

## Phase 5: Simulation lab
Monte Carlo (bootstrap / GBM / resampled strategy trades), Black-Scholes with Greeks and sensitivity charts, step-by-step strategy replay (no look-ahead) and what-if market scenarios. All simulated output is labelled synthetic or theoretical.

## Phase 6: Portfolio & risk, Trade history
Both pages use only MT5 account data, positions and deal history plus this app's own trade records. With MT5 disconnected they say so instead of estimating. Exit prices and P&L of app trades are written back to the app database once MT5 history is available.

## Walk-forward evaluation
`cd backend && python walkforward.py <EURUSD_M5.csv>` (~7-20 min, resumable) writes `models/walkforward.json`, shown on the Research tab. Six pre-specified configurations, rolling retrain, contiguous out-of-sample folds, random-entry baseline, pooled-trade confidence intervals. All results are reported; none is selected afterwards.

## Settings & indicators
Settings tab: MT5 status/reconnect (demo-only is set in `backend/.env`, deliberately not switchable in the UI), default symbol/timeframe, favourites, chart preferences, strategy and simulation defaults, notifications, and the risk limits (validated, saved to the database, restored on restart). Terminal: SMA, EMA, Bollinger Bands, VWAP, volume MA, RSI, MACD, ATR and OBV, computed from the chart's bars; several of each can be added and configured, and they are remembered.

## Chart tools, alerts, volatility filter
Terminal toolbar: horizontal line, trend line, support, resistance and price alert tools (click the chart; Esc cancels), saved per symbol and timeframe. Alerts are checked against live MT5 bids while the page is open. Risk engine: optional volatility filter on ATR(14) of M5 bars (Settings > Risk parameters).

## Auto-trader (demo only)
Terminal sidebar > Auto-trader. Off by default; start it explicitly. Once per newly closed candle it takes the model's decision, builds an ATR-based stop-loss/take-profit, sizes the lot from your risk-per-trade limit and sends the order through the same guarded path as manual orders (demo guard, risk engine, MT5 check), tagged 'strategy' (magic 5151). It manages only its own positions, stops after 3 consecutive failed orders or errors, enforces a daily trade cap, and has a Stop / Stop-and-close kill switch. It never restarts by itself after a backend restart. The strategy lost money in testing, so this is a pipeline demonstration.
