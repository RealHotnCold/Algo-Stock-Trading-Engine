"""STRATEGY/MANUAL -> demo guard -> risk -> MT5 order_check -> order_send -> DB. Frontend never talks to MT5."""
import time, logging, datetime as dt
from ..mt5.gateway import trading_allowed, DONE_CODES, MT5Unavailable
from ..risk.engine import RiskConfig, evaluate, atr_points
from ..db import Session, Trade

log = logging.getLogger("execution")

class ExecutionService:
    def __init__(self, gw, cfg: RiskConfig | None = None):
        self.gw, self.cfg = gw, cfg or RiskConfig()

    def _context(self, o):
        st = self.gw.status()
        if not st["connected"]: raise MT5Unavailable(st.get("reason", "disconnected"))
        return st, self.gw.spec(o["symbol"]), self.gw.tick(o["symbol"]), self.gw.positions()

    def validate(self, o: dict) -> dict:
        try: return self._validate(o)
        except Exception as e:                       # never a bare 500: show the real cause in the UI
            log.exception("validate failed"); return {"stage": "backend_error", "approved": False, "reason": f"{type(e).__name__}: {e}"}

    def _validate(self, o: dict) -> dict:
        try: st, spec, tick, pos = self._context(o)
        except MT5Unavailable as e: return {"stage": "connection", "approved": False, "reason": str(e)}
        ok, why = trading_allowed(st["account"]["kind"], st["demo_only"], None)
        if not ok: return {"stage": "account_guard", "approved": False, "reason": why}
        atr = None
        if self.cfg.vol_filter:
            try: atr = atr_points(self.gw.bars(o["symbol"], "M5", 60), spec)
            except Exception: atr = None          # any failure => filter fails safe
        risk = evaluate(self.cfg, o, account=st["account"], positions=pos, spec=spec, tick=tick,
                        daily_pnl=self.gw.daily_pnl(), utc_hour=dt.datetime.now(dt.timezone.utc).hour, atr_points=atr)
        if not risk["approved"]:
            return {"stage": "risk", "approved": False, "reason": "; ".join(c["detail"] for c in risk["checks"] if not c["passed"]), "risk": risk}
        chk = self.gw.order_check(o, spec)
        okc = chk["retcode"] == 0 or chk["retcode"] in DONE_CODES  # order_check returns 0 when OK
        return {"stage": "broker_check", "approved": okc, "reason": None if okc else chk["comment"], "risk": risk, "broker_check": chk}

    def submit(self, o: dict, source: str = "manual", confidence: float | None = None, infer_ms: float | None = None) -> dict:
        v = self.validate(o)
        if not v["approved"]: return {"executed": False, **v}
        t0 = time.perf_counter()
        try: res = self.gw.order_send(o, self.gw.spec(o["symbol"]))
        except Exception as e:
            log.exception("order_send failed"); return {"executed": False, "stage": "backend_error", "reason": f"{type(e).__name__}: {e}. Check MT5 before retrying: the order may or may not have been sent."}
        exec_ms = (time.perf_counter() - t0) * 1000
        if res["retcode"] not in DONE_CODES:      # never report success on a rejected order
            return {"executed": False, "stage": "execution", "reason": f"{res['retcode']}: {res['comment']}", "result": res, "latency_exec_ms": exec_ms}
        with Session() as s, s.begin():
            s.add(Trade(ticket=res["order"] or res["deal"], symbol=o["symbol"], direction=o["side"], volume=res["volume"] or o["volume"],
                        entry_price=res["price"] or None, entry_time=int(time.time()), source=source, confidence=confidence,
                        latency_infer_ms=infer_ms, latency_exec_ms=exec_ms))
        return {"executed": True, "result": res, "state": DONE_CODES[res["retcode"]], "risk": v["risk"],
                "latency_infer_ms": infer_ms, "latency_exec_ms": exec_ms}
