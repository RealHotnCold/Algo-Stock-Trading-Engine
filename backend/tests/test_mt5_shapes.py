"""Runs the REAL gateway + execution code against a fake `MetaTrader5` module shaped like the documented API
(order_check results have NO order/deal/price/volume fields; deals/positions are attribute objects)."""
import os; os.environ.setdefault("DB_URL", "sqlite:///./data/test.db")
from types import SimpleNamespace as NS
from app.db import init_db
from app.mt5.gateway import MT5Gateway
from app.execution.service import ExecutionService
from app.risk.engine import RiskConfig

class FakeMT5:
    TRADE_ACTION_DEAL, TRADE_ACTION_PENDING = 1, 5
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT, ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 0, 1, 2, 3, 4, 5
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN, ORDER_TIME_GTC = 0, 1, 2, 0
    def __init__(s, check_code=0, send_code=10009): s.check_code, s.send_code, s.sent, s.positions = check_code, send_code, [], []
    def initialize(s, **kw): return True
    def last_error(s): return (1, "ok")
    def terminal_info(s): return NS(connected=True)
    def account_info(s): return NS(login=1, server="Demo", company="Broker", currency="USD", trade_mode=0, balance=10000.0, equity=10000.0, margin=0.0, margin_free=10000.0, leverage=100)
    def symbol_info(s, sym): return NS(name=sym, description="d", path="p", digits=5, point=1e-5, trade_tick_size=1e-5, trade_tick_value=1.0, trade_contract_size=100000.0, volume_min=0.01, volume_max=100.0,
                                       volume_step=0.01, filling_mode=2, trade_stops_level=10, trade_mode=4, spread=10, visible=True)
    def symbol_info_tick(s, sym): return NS(bid=1.1000, ask=1.1001, last=0.0, time=1700000000)
    def symbol_select(s, sym, on): return True
    def positions_get(s, **kw): return [p for p in s.positions if kw.get("ticket") in (None, p.ticket)]
    def history_deals_get(s, a, b): return []
    def order_check(s, req): return NS(retcode=s.check_code, balance=10000.0, equity=10000.0, profit=0.0, margin=110.0, margin_free=9890.0, margin_level=0.0, comment="Done", request=req)   # no order/deal/price/volume
    def order_send(s, req):
        s.sent.append(req)
        if "position" in req: s.positions = [p for p in s.positions if p.ticket != req["position"]]          # closing order
        elif s.send_code in (10009, 10008): s.positions.append(NS(ticket=555, symbol=req["symbol"], type=0 if req["type"] in (0, 2, 4) else 1, volume=req["volume"], price_open=1.1001, sl=req["sl"], tp=req["tp"], profit=0.0, time=1, magic=req["magic"]))
        return NS(retcode=s.send_code, deal=9, order=555, volume=req["volume"], price=1.1001, bid=1.1, ask=1.1001, comment="Request executed", request_id=1, retcode_external=0)

def make(**kw):
    init_db(); g = MT5Gateway(); g._mt5 = FakeMT5(**kw); return g, ExecutionService(g, RiskConfig())
ORD = dict(symbol="EURUSD", side="buy", volume=0.10, order_type="market", sl=1.0951, tp=1.1101)

def test_validate_and_execute_through_real_gateway_code():
    g, exe = make(); v = exe.validate(ORD); assert v["approved"] and v["stage"] == "broker_check" and v["broker_check"]["retcode"] == 0   # used to crash on missing attributes
    r = exe.submit(ORD); assert r["executed"] and r["result"]["order"] == 555 and g._mt5.sent[0]["type_filling"] == FakeMT5.ORDER_FILLING_IOC and g._mt5.sent[0]["magic"] == 5150
    assert g.positions()[0]["ticket"] == 555 and g.positions()[0]["magic"] == 5150

def test_broker_rejections_are_reported_not_crashes():
    g, exe = make(check_code=10019); v = exe.validate(ORD); assert not v["approved"] and v["stage"] == "broker_check"
    g, exe = make(send_code=10006); r = exe.submit(ORD); assert r["executed"] is False and r["stage"] == "execution"

def test_pending_orders_and_close():
    g, exe = make(); r = exe.submit({**ORD, "order_type": "limit", "price": 1.0990}); assert r["executed"] and g._mt5.sent[0]["action"] == 5 and g._mt5.sent[0]["price"] == 1.0990
    assert g.close_position(555)["retcode"] == 10009 and g._mt5.sent[-1]["position"] == 555

def test_unexpected_errors_become_readable_messages_not_500s():
    g, exe = make(); g._mt5.symbol_info = lambda s: 1 / 0
    v = exe.validate(ORD); assert not v["approved"] and "ZeroDivisionError" in v["reason"]
    r = exe.submit(ORD); assert not r["executed"] and "ZeroDivisionError" in r["reason"]
