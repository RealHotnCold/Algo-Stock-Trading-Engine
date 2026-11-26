import os; os.environ.setdefault("DB_URL", "sqlite:///./data/test.db")
import pytest
from app.db import init_db
from app.execution.autotrader import AutoTrader, MAGIC
from app.execution.service import ExecutionService
from app.risk.engine import RiskConfig
from tests.test_phase2 import SPEC, TICK

class FG:
    def __init__(s): s.kind, s.n, s.pos, s.sent, s.closed, s.code = "demo", 500, [], [], [], 10009
    def status(s): return {"connected": True, "demo_only": True, "trading_allowed": s.kind == "demo", "trading_reason": "x", "account": dict(kind=s.kind, equity=10000, balance=10000, currency="USD", login=1)}
    def bars(s, sym, tf, n): return [dict(time=300 * i, open=1.1, high=1.1005, low=1.0995, close=1.1, volume=1.0, spread=0) for i in range(s.n)]   # last one = forming candle
    def positions(s): return s.pos
    def spec(s, _): return dict(SPEC)
    def tick(s, _): return TICK
    def daily_pnl(s): return 0.0
    def order_check(s, o, sp): return {"retcode": 0, "comment": "ok"}
    def order_send(s, o, sp):
        s.sent.append(o); ok = s.code == 10009
        if ok: s.pos.append(dict(ticket=100 + len(s.sent), symbol=o["symbol"], side=o["side"], volume=o["volume"], magic=o["magic"], price_open=1.1, sl=o["sl"], tp=o["tp"], profit=0.0))
        return {"retcode": s.code, "comment": "x", "order": 100 + len(s.sent), "deal": 1, "price": 1.1001, "volume": o["volume"]}
    def close_position(s, t): s.closed.append(t); s.pos = [p for p in s.pos if p["ticket"] != t]; return {"retcode": 10009, "comment": ""}
class FM:
    target, conf = 1, 0.7
    def explain(s, df, pos=0): return dict(regime="up/high", decision="Buy" if s.target > 0 else "No trade", confidence=s.conf, target_position=s.target)

def make(max_trades=5, cfg=None):
    init_db(); g, m = FG(), FM(); a = AutoTrader(g, ExecutionService(g, cfg or RiskConfig()), lambda tf: m, lambda: {"sl_atr": 2.0, "tp_atr": 3.0}); return g, m, a
def new_bar(g, a): g.n += 1; a._cycle()

def test_start_guards():
    g, m, a = make(); g.kind = "real"
    with pytest.raises(ValueError, match="demo"): a.start("EURUSD", "M5", spawn=False)
    g.kind = "demo"
    for args in (("GBPUSD", "M5"), ("EURUSD", "M1"), ("EURUSD", "M5", 0), ("EURUSD", "M5", 99)):
        with pytest.raises(ValueError): a.start(*args, spawn=False)
    a.start("EURUSD", "M5", spawn=False)
    with pytest.raises(ValueError, match="already"): a.start("EURUSD", "M5", spawn=False)

def test_trades_only_on_new_closed_candle_and_manages_position():
    g, m, a = make(); a.start("EURUSD", "M5", spawn=False); a._cycle(); assert not g.sent                 # same candle as at start: nothing
    new_bar(g, a); assert len(g.sent) == 1
    o = g.sent[0]; assert o["side"] == "buy" and o["sl"] < 1.1001 < o["tp"] and o["magic"] == MAGIC and o["volume"] > 0
    a._cycle(); assert len(g.sent) == 1                                                                   # one decision per candle
    new_bar(g, a); assert len(g.sent) == 1 and not g.closed                                               # already long: nothing
    m.target = 0; new_bar(g, a); assert len(g.closed) == 1 and not g.pos                                  # target flat -> close
    m.target = -1; new_bar(g, a); assert g.sent[-1]["side"] == "sell"
    m.target = 1; new_bar(g, a); assert len(g.closed) == 2 and g.sent[-1]["side"] == "buy"                # flip = close then open

def test_ignores_manual_positions_and_daily_limit():
    g, m, a = make(); g.pos = [dict(ticket=1, symbol="EURUSD", side="sell", volume=0.1, magic=5150, price_open=1.1, sl=0, tp=0, profit=0.0)]
    a.start("EURUSD", "M5", max_trades_per_day=1, spawn=False); new_bar(g, a); assert len(g.sent) == 1 and 1 not in g.closed       # manual position untouched
    m.target = -1; new_bar(g, a); assert len(g.sent) == 1 and len(g.closed) == 1                                                     # closes its own, but daily limit blocks the new one

def test_risk_veto_is_not_a_failure_but_execution_errors_stop_it():
    g, m, a = make(cfg=RiskConfig(max_open_positions=1)); g.pos = [dict(ticket=1, symbol="EURUSD", side="sell", volume=0.1, magic=5150, price_open=1.1, sl=0, tp=0, profit=0.0)]
    a.start("EURUSD", "M5", spawn=False); new_bar(g, a); assert not g.sent and a.failures == 0 and "blocked at risk" in a.log[-1]["msg"]
    g2, m2, a2 = make(); g2.code = 10006; a2.start("EURUSD", "M5", spawn=False)
    for _ in range(3): new_bar(g2, a2)
    assert not a2.running and a2.failures == 3

def test_kill_switch_closes_only_strategy_positions():
    g, m, a = make(); a.start("EURUSD", "M5", spawn=False); new_bar(g, a)
    g.pos.append(dict(ticket=7, symbol="EURUSD", side="buy", volume=0.1, magic=5150, price_open=1.1, sl=0, tp=0, profit=0.0))
    s = a.stop(close_positions=True); assert not s["running"] and g.closed == [101] and [p["ticket"] for p in g.pos] == [7]
    new_bar(g, a); assert len(g.sent) == 1                                                                 # stopped: no more orders

def test_lot_size_is_capped_to_exposure_limits_instead_of_being_vetoed():
    g, m, a = make(); g.status = lambda: {"connected": True, "demo_only": True, "trading_allowed": True, "trading_reason": "x", "account": dict(kind="demo", equity=1_000_000, balance=1_000_000, currency="USD", login=1)}
    a.start("EURUSD", "M5", spawn=False); new_bar(g, a)
    assert len(g.sent) == 1 and g.sent[0]["volume"] == 1.0 and "capped" in " ".join(l["msg"] for l in a.log)        # risk sizing wanted ~50 lots; default cap is 1 lot per symbol

def test_preview_places_nothing_and_shows_checks():
    g, m, a = make(); p = a.preview("EURUSD", "M5")
    assert not g.sent and p["order"]["side"] == "buy" and p["validation"]["approved"] and p["target"] == 1 and p["current"] == 0 and not a.running
    m.target = 0; p = a.preview("EURUSD", "M5"); assert p["order"] is None and "flat" in p["note"]
    with pytest.raises(ValueError): a.preview("GBPUSD", "M5")

def test_heartbeat_and_next_candle():
    g, m, a = make(); a.start("EURUSD", "M5", spawn=False); a._cycle(); s = a.status()
    assert s["last_check"] and s["next_candle_close"] == 300 * 498 + 600
