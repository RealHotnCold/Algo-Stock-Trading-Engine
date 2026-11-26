import os; os.environ["DB_URL"] = "sqlite:///./data/test.db"
from app.db import init_db; init_db()
from app.risk.engine import RiskConfig, evaluate, size_by_risk
from app.execution.service import ExecutionService
from app.mt5.gateway import pick_filling

SPEC = dict(symbol="EURUSD", digits=5, point=1e-5, tick_size=1e-5, tick_value=1.0, contract_size=100000, vol_min=0.01, vol_max=100, vol_step=0.01, filling="IOC")
TICK = dict(symbol="EURUSD", bid=1.1000, ask=1.1001, spread_points=10, time=0, digits=5, market_open=True)

class Fake:
    def __init__(s, kind="demo", send_code=10009, pos=()): s.kind, s.code, s.pos, s.sent = kind, send_code, list(pos), 0
    def status(s): return {"connected": True, "demo_only": True, "account": dict(kind=s.kind, equity=10000, balance=10000, currency="USD")}
    def spec(s, _): return SPEC
    def tick(s, _): return TICK
    def positions(s): return s.pos
    def daily_pnl(s): return 0.0
    def order_check(s, o, sp): return {"retcode": 0, "comment": "ok"}
    def order_send(s, o, sp): s.sent += 1; return {"retcode": s.code, "comment": "x", "order": 1, "deal": 1, "price": 1.1001, "volume": o["volume"]}

ORD = dict(symbol="EURUSD", side="buy", volume=0.10, sl=1.0951, tp=1.1101)  # 100 pips SL on 0.10 lot = $100 = 1%

def test_sizing():
    assert size_by_risk(10000, 1, 1.1001, 1.0951, SPEC) == 0.2   # $100 / (500 ticks*$1) = 0.2 lot
    assert size_by_risk(10000, 1, 1.1001, 1.1001, SPEC) == 0.0

def test_pass_and_executes():
    g = Fake(); r = ExecutionService(g).submit(ORD); assert r["executed"] and g.sent == 1

def test_real_account_blocked_before_risk():
    g = Fake(kind="real"); r = ExecutionService(g).submit(ORD); assert not r["executed"] and r["stage"] == "account_guard" and g.sent == 0

def test_risk_veto():
    g = Fake(); r = ExecutionService(g).submit({**ORD, "volume": 0.5}); assert not r["executed"] and r["stage"] == "risk" and g.sent == 0
    r = ExecutionService(g).submit({k: v for k, v in ORD.items() if k != "sl"}); assert r["stage"] == "risk"
    r = ExecutionService(g).submit({**ORD, "sl": 1.1051}); assert r["stage"] == "risk"   # SL above entry on a buy
    g2 = Fake(pos=[dict(symbol="EURUSD", volume=0.95)]); assert ExecutionService(g2).submit(ORD)["stage"] == "risk"

def test_broker_reject_not_reported_as_success():
    g = Fake(send_code=10006); r = ExecutionService(g).submit(ORD); assert r["executed"] is False and r["stage"] == "execution"

def test_spread_and_session():
    c = evaluate(RiskConfig(max_spread_points=5, session_utc_hours=(8, 17)), ORD, account=dict(equity=10000, balance=10000, currency="USD"),
                 positions=[], spec=SPEC, tick=TICK, daily_pnl=0, utc_hour=3)
    bad = {x["name"] for x in c["checks"] if not x["passed"]}; assert bad == {"spread", "session"}

def test_daily_loss():
    c = evaluate(RiskConfig(), ORD, account=dict(equity=9600, balance=10000, currency="USD"), positions=[], spec=SPEC, tick=TICK, daily_pnl=-400, utc_hour=10)
    assert not c["approved"] and any(x["name"] == "daily_loss" and not x["passed"] for x in c["checks"])

def test_filling():
    assert (pick_filling(1), pick_filling(2), pick_filling(3), pick_filling(0)) == ("FOK", "IOC", "FOK", "RETURN")
