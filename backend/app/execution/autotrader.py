"""Demo-only automatic trading loop (a pipeline demonstration; the strategy has no demonstrated edge).
Once per newly CLOSED candle: model decision -> the SAME validated path as manual orders (demo guard, risk engine, MT5 check, send), source 'strategy', magic 5151.
Off by default, never restarts by itself, stops on repeated execution failures, and can be killed at any time."""
import datetime as dt, math, threading, time
import pandas as pd
from ..risk.engine import size_by_risk, atr_points

MAGIC, MODEL_TFS, OK_CODES = 5151, ("M5", "M15", "H1"), (10009, 10008)
TF_SEC = {"M5": 300, "M15": 900, "H1": 3600}

class AutoTrader:
    def __init__(self, gw, exe, get_model, get_cfg, poll_s=5):
        self.gw, self.exe, self.get_model, self.get_cfg, self.poll_s = gw, exe, get_model, get_cfg, poll_s
        self.lock = threading.RLock(); self._stop = threading.Event(); self.running = False; self.symbol = self.tf = None
        self.max_trades = 5; self.failures = 0; self.last_bar = None; self.last_decision = None; self.last_check = None; self.started_at = None; self.log = []; self._day = None; self._n = 0; self._down = False

    def _log(self, msg): self.log.append({"t": int(time.time()), "msg": msg}); del self.log[:-100]
    def _bars(self):
        b = self.gw.bars(self.symbol, self.tf, 800)[:-1]                       # last element is the still-forming candle
        if len(b) < 400: raise ValueError("need at least 400 closed bars")
        return b
    def _mine(self): return [p for p in self.gw.positions() if p["symbol"] == self.symbol and p.get("magic") == MAGIC]
    def _today(self):
        d = dt.datetime.now(dt.timezone.utc).date()
        if d != self._day: self._day, self._n = d, 0
        return self._n

    def start(self, symbol, tf, max_trades_per_day=5, spawn=True):
        with self.lock:
            if self.running: raise ValueError("already running")
            if not str(symbol).upper().startswith("EURUSD"): raise ValueError("the model is trained on EURUSD only")
            if tf not in MODEL_TFS: raise ValueError(f"timeframe must be one of {MODEL_TFS}")
            if not isinstance(max_trades_per_day, int) or not 1 <= max_trades_per_day <= 50: raise ValueError("max trades per day must be 1 to 50")
            st = self.gw.status()
            if not st["connected"]: raise ValueError("MT5 is not connected")
            if st["account"]["kind"] != "demo" or not st["trading_allowed"]: raise ValueError("automatic trading runs on demo accounts only")
            self.get_model(tf)                                                 # fails early if no trained model
            self.symbol, self.tf, self.max_trades, self.failures, self._down = symbol, tf, max_trades_per_day, 0, False
            self.last_bar = self._bars()[-1]["time"]                           # prime: only candles that close AFTER start are traded
            self.last_decision, self.log, self.running, self.started_at = None, [], True, int(time.time()); self._stop.clear()
            self._log(f"started on {symbol} {tf}, max {max_trades_per_day} new trades per day; waiting for the next candle to close")
            if spawn: threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop.is_set():
            try: self._cycle()
            except Exception as e:
                self.failures += 1; self._log(f"error: {type(e).__name__}: {e}")
                if self.failures >= 3: self._halt("stopped after 3 consecutive errors or failed orders")
            self._stop.wait(self.poll_s)

    def _halt(self, why): self._log(why); self._stop.set(); self.running = False

    def _cycle(self):
        with self.lock:
            if not self.running: return
            if not self.gw.status()["connected"]:
                if not self._down: self._log("MT5 disconnected: waiting"); self._down = True
                return
            self._down = False; bars = self._bars(); bt = bars[-1]["time"]; self.last_check = int(time.time())
            if bt == self.last_bar: return
            self.last_bar = bt; mine = self._mine(); net = sum(p["volume"] * (1 if p["side"] == "buy" else -1) for p in mine); cur = (net > 0) - (net < 0)
            t0 = time.perf_counter(); e = self.get_model(self.tf).explain(pd.DataFrame(bars), pos=cur); infer = (time.perf_counter() - t0) * 1000; target = e["target_position"]
            self.last_decision = dict(bar=bt, regime=e["regime"], decision=e["decision"], confidence=e["confidence"], target=target, current=cur)
            self._log(f"candle {dt.datetime.fromtimestamp(bt, dt.timezone.utc):%m-%d %H:%M}: {e['decision']} (confidence {e['confidence'] * 100:.0f}%, regime {e['regime']}); target {target:+d}, holding {cur:+d}{' (nothing to do)' if target == cur else ''}")
            if target == cur: return
            if cur != 0: self._close(mine)
            if target != 0: self._open(bars, e, target, infer)

    def _close(self, mine):
        for p in mine:
            r = self.gw.close_position(p["ticket"])
            if r["retcode"] in OK_CODES: self._log(f"closed position {p['ticket']}")
            else: self._fail(f"close failed ({r['retcode']}: {r.get('comment')})")

    def _fail(self, msg):
        self.failures += 1; self._log(msg)
        if self.failures >= 3: self._halt("stopped after 3 consecutive errors or failed orders")

    def _plan(self, bars, target, closing=False):
        """The order a target position implies: ATR-based stop/target, lot sized from risk, then capped to the exposure room your risk limits leave."""
        spec, tick, acc = self.gw.spec(self.symbol), self.gw.tick(self.symbol), self.gw.status()["account"]; cfg = self.get_cfg(); buy = target > 0
        a = atr_points(bars[-60:], spec)
        if a is None: return None, "ATR unavailable (need recent bars)"
        d = a * spec["point"]; entry = tick["ask"] if buy else tick["bid"]; sign = 1 if buy else -1
        sl, tp = round(entry - sign * cfg["sl_atr"] * d, spec["digits"]), round(entry + sign * cfg["tp_atr"] * d, spec["digits"])
        vol = size_by_risk(acc["equity"], self.exe.cfg.risk_per_trade_pct, entry, sl, spec)
        if vol <= 0: return None, "lot size below the broker minimum for this risk"
        held = [p for p in self.gw.positions() if not (closing and p["symbol"] == self.symbol and p.get("magic") == MAGIC)]; rc = self.exe.cfg
        room = min(rc.max_lots_per_symbol - sum(p["volume"] for p in held if p["symbol"] == self.symbol), rc.max_total_lots - sum(p["volume"] for p in held))
        cap = math.floor(room / spec["vol_step"] + 1e-9) * spec["vol_step"]; note = ""
        if cap < vol: vol = round(max(cap, 0.0), 8); note = f"lot size capped to {vol} by your exposure limits"
        if vol < spec["vol_min"]: return None, "no room left under your exposure limits (max lots)"
        return dict(symbol=self.symbol, side="buy" if buy else "sell", volume=vol, order_type="market", sl=sl, tp=tp, magic=MAGIC, comment="strategy"), note

    def _open(self, bars, e, target, infer, closing=False):
        if self._today() >= self.max_trades: self._log("daily trade limit reached: not opening"); return
        o, note = self._plan(bars, target, closing)
        if o is None: self._log(f"not opening: {note}"); return
        r = self.exe.submit(o, source="strategy", confidence=e["confidence"], infer_ms=infer)
        if r["executed"]: self._n += 1; self.failures = 0; self._log(f"opened {o['side']} {o['volume']} lots, SL {o['sl']}, TP {o['tp']}, MT5 {r['latency_exec_ms']:.0f} ms" + (f" ({note})" if note else ""))
        elif r["stage"] in ("execution", "backend_error"): self._fail(f"order failed: {r['reason']}")
        else: self._log(f"order blocked at {r['stage']}: {r.get('reason')}")      # a risk veto is a normal outcome, not a failure

    def preview(self, symbol, tf):
        """What the auto-trader would do right now, including the risk checks, WITHOUT placing anything."""
        if not str(symbol).upper().startswith("EURUSD") or tf not in MODEL_TFS: raise ValueError("the model is trained on EURUSD, M5, M15 and H1 only")
        if not self.gw.status()["connected"]: raise ValueError("MT5 is not connected")
        model = self.get_model(tf)
        with self.lock:
            saved = (self.symbol, self.tf)
            if not self.running: self.symbol, self.tf = symbol, tf
            try:
                bars = self._bars(); mine = self._mine(); net = sum(p["volume"] * (1 if p["side"] == "buy" else -1) for p in mine); cur = (net > 0) - (net < 0)
                e = model.explain(pd.DataFrame(bars), pos=cur); target = e["target_position"]
                out = dict(symbol=self.symbol, tf=self.tf, bar_time=bars[-1]["time"], decision=e["decision"], confidence=e["confidence"], regime=e["regime"], target=target, current=cur, order=None, validation=None, note="")
                if target == cur: out["note"] = "Already holding what the model wants: nothing to do." if cur else "The model says stay flat: nothing to do."
                else:
                    o, note = self._plan(bars, target, closing=cur != 0)
                    if o is None: out["note"] = note
                    else: out["order"], out["validation"] = o, self.exe.validate(o); out["note"] = ("It would first close its current position. " if cur else "") + note
                return out
            finally:
                if not self.running: self.symbol, self.tf = saved

    def stop(self, close_positions=False):
        with self.lock:
            was = self.running; self._stop.set(); self.running = False
            if was: self._log("stopped by user")
            if close_positions and self.symbol:
                mine = self._mine(); self._close(mine) if mine else self._log("no strategy positions to close")
        return self.status()

    def status(self):
        nxt = self.last_bar + 2 * TF_SEC[self.tf] if self.running and self.last_bar and self.tf in TF_SEC else None
        return dict(running=self.running, last_check=self.last_check, next_candle_close=nxt, symbol=self.symbol, tf=self.tf, started_at=self.started_at, trades_today=self._n if self._day == dt.datetime.now(dt.timezone.utc).date() else 0,
                    max_trades_per_day=self.max_trades, consecutive_failures=self.failures, last_decision=self.last_decision, log=self.log[-40:])
