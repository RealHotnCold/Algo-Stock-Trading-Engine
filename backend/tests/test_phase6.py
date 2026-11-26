import os; os.environ.setdefault("DB_URL", "sqlite:///./data/test.db")
from fastapi.testclient import TestClient
from app import main
from app.db import init_db, Session, Trade
from app.portfolio import analytics as an
from app.mt5.gateway import MT5Unavailable

def D(t, tk, typ, entry, pid, vol, price, profit=0.0, comm=0.0, order=None, magic=0, sym="EURUSD"):
    return dict(ticket=tk, order=order or tk, time=t, type=typ, entry=entry, position_id=pid, volume=vol, price=price, commission=comm, swap=0.0, profit=profit, symbol=sym, magic=magic, comment="")

DEALS = [D(100, 1, 2, 0, 0, 0, 0, profit=10000.0, sym=""),                                   # deposit (balance op)
         D(1000, 2, 0, 0, 11, 0.2, 1.1000, comm=-1.0), D(2000, 3, 1, 1, 11, 0.2, 1.1050, profit=100.0, comm=-1.0),   # buy win +98
         D(3000, 4, 1, 0, 12, 0.1, 1.1000, comm=-0.5, magic=5150), D(4000, 5, 0, 1, 12, 0.1, 1.1030, profit=-30.0, comm=-0.5, magic=5150),  # sell loss -31
         D(5000, 6, 0, 0, 13, 0.1, 1.1000)]                                                  # still open

def test_pair_deals_and_stats():
    t = {x["position_id"]: x for x in an.pair_deals(DEALS)}
    assert t[11]["side"] == "buy" and t[11]["status"] == "closed" and abs(t[11]["profit"] - 98) < 1e-9 and t[11]["exit_price"] == 1.105
    assert t[12]["side"] == "sell" and abs(t[12]["profit"] + 31) < 1e-9 and t[13]["status"] == "open" and 0 not in t
    s = an.trade_stats(list(t.values())); assert s["n"] == 2 and s["wins"] == 1 and abs(s["profit_factor"] - 98 / 31) < 1e-9 and abs(s["net"] - 67) < 1e-9

def test_balance_curve_anchor_and_drawdown():
    pts, mdd = an.balance_curve(DEALS, 10067.0); assert abs(pts[-1][1] - 10067.0) < 1e-9 and abs(pts[0][1] - 0.0) < 1e-9
    pts, mdd = an.balance_curve([d for d in DEALS if d["type"] != 2], 10067.0); assert abs(pts[0][1] - 10000.0) < 1e-9 and mdd > 0   # 98 up then -31 => drawdown
    assert an.daily_pnl(an.pair_deals(DEALS))[0]["date"] == "1970-01-01"

class FG:
    def __init__(s, up=True): s.up = up
    def status(s): return {"connected": True, "account": dict(login=1, server="x", broker="b", currency="USD", kind="demo", balance=10067.0, equity=10077.0, margin=100.0, margin_free=9977.0, leverage=100)} if s.up else {"connected": False, "reason": "no terminal"}
    def deals(s, days):
        if not s.up: raise MT5Unavailable("no terminal")
        return DEALS
    def positions(s): return [dict(ticket=13, symbol="EURUSD", side="buy", volume=0.1, price_open=1.1, sl=1.095, tp=0, profit=10.0, time=5000)]
    def spec(s, _): return dict(tick_size=1e-5, tick_value=1.0, contract_size=100000)
    def daily_pnl(s): return -20.0

def test_endpoints_with_fake_mt5(monkeypatch):
    init_db()
    with Session() as s, s.begin(): s.add(Trade(ticket=11, symbol="EURUSD", direction="buy", volume=0.2, entry_price=1.1, source="strategy", confidence=0.7, latency_exec_ms=120.0)); s.add(Trade(ticket=999, symbol="EURUSD", direction="sell", volume=0.1, source="manual"))
    monkeypatch.setattr(main, "gw", FG()); c = TestClient(main.app)
    p = c.get("/api/portfolio").json(); assert p["connected"] and abs(p["positions"][0]["risk_at_stop"] - 50.0) < 1e-6 and p["exposure"][0]["long_lots"] == 0.1 and p["limits"]["open_positions"][0] == 1
    assert p["pnl"]["unrealized"] == 10.0 and p["stats"]["n"] == 2 and p["limits"]["daily_loss"][0] == 20.0
    with Session() as s: id11 = s.scalars(__import__("sqlalchemy").select(Trade).where(Trade.ticket == 11)).first().id; id999 = s.scalars(__import__("sqlalchemy").select(Trade).where(Trade.ticket == 999)).first().id
    r = {x["id"]: x for x in c.get("/api/trades").json()["rows"]}
    assert r["mt5-11"]["source"] == "strategy" and r["mt5-11"]["confidence"] == 0.7 and r["mt5-12"]["source"] == "app (no record)" and r[f"app-{id999}"]["status"] == "unconfirmed"
    with Session() as s: t = s.get(Trade, id11); assert t.exit_price == 1.105 and abs(t.profit - 98) < 1e-9        # exit data synced into the app DB
    monkeypatch.setattr(main, "gw", FG(up=False)); off = c.get("/api/trades").json(); assert off["mt5_available"] is False and any(x["id"] == f"app-{id11}" and x["status"] == "closed" for x in off["rows"])
    assert c.get("/api/portfolio").json()["connected"] is False
