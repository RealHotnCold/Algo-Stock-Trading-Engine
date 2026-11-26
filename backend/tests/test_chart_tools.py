import os; os.environ.setdefault("DB_URL", "sqlite:///./data/test.db")
from fastapi.testclient import TestClient
from app import main
from app.risk.engine import RiskConfig, evaluate, atr_points
from app.execution.service import ExecutionService
from tests.test_phase2 import Fake, ORD, SPEC, TICK

def bars(n=40, rng=0.0010): return [dict(time=i, open=1.1, high=1.1 + rng / 2, low=1.1 - rng / 2, close=1.1) for i in range(n)]
ACC = dict(equity=10000, balance=10000, currency="USD")
def ev(cfg, atr): return evaluate(cfg, ORD, account=ACC, positions=[], spec=SPEC, tick=TICK, daily_pnl=0, utc_hour=10, atr_points=atr)
def failed(r): return {c["name"] for c in r["checks"] if not c["passed"]}

def test_atr_points_value_and_unavailable():
    assert abs(atr_points(bars(), SPEC) - 100.0) < 1e-6          # constant 0.0010 range, point 1e-5 -> 100 points
    assert atr_points(bars(10), SPEC) is None

def test_volatility_filter():
    assert "volatility" not in {c["name"] for c in ev(RiskConfig(), 5)["checks"]}                  # off by default
    cfg = RiskConfig(vol_filter=True, min_atr_points=50, max_atr_points=200)
    assert not failed(ev(cfg, 100)) and failed(ev(cfg, 20)) == {"volatility"} and failed(ev(cfg, 400)) == {"volatility"} and failed(ev(cfg, None)) == {"volatility"}
    assert not failed(ev(RiskConfig(vol_filter=True, min_atr_points=50, max_atr_points=0), 5000))   # 0 = no upper cap

def test_execution_uses_recent_bars_for_volatility():
    class G(Fake):
        def bars(s, sym, tf, n): return bars()
    ok = ExecutionService(G(), RiskConfig(vol_filter=True, min_atr_points=50)).submit(ORD); assert ok["executed"]
    low = ExecutionService(G(), RiskConfig(vol_filter=True, min_atr_points=500)).submit(ORD); assert not low["executed"] and low["stage"] == "risk"
    nodata = ExecutionService(Fake(), RiskConfig(vol_filter=True)).submit(ORD); assert not nodata["executed"]      # Fake has no bars(): filter fails safe

def test_drawings_roundtrip_and_validation():
    items = [{"id": "a1", "type": "hline", "price": 1.1}, {"id": "b2", "type": "trend", "t1": 1, "p1": 1.1, "t2": 5, "p2": 1.12, "evil": "x"}, {"id": "c3", "type": "alert", "price": 1.15, "dir": "above"}]
    with TestClient(main.app) as c:
        r = c.put("/api/drawings", params={"symbol": "EURUSD", "tf": "M5"}, json={"items": items}).json()["items"]; assert "evil" not in r[1] and r[2]["triggered"] is False
        assert c.get("/api/drawings", params={"symbol": "EURUSD", "tf": "M5"}).json()["items"] == r and c.get("/api/drawings", params={"symbol": "EURUSD", "tf": "H1"}).json()["items"] == []
        for bad in ([{"id": "x", "type": "nope", "price": 1}], [{"id": "x", "type": "hline", "price": -1}], [{"id": "x", "type": "alert", "price": 1}], [{"id": "x", "type": "trend", "t1": 1}], "str"):
            assert c.put("/api/drawings", params={"symbol": "EURUSD", "tf": "M5"}, json={"items": bad}).status_code == 400
        assert c.put("/api/drawings", params={"symbol": "bad symbol!", "tf": "M5"}, json={"items": []}).status_code == 400
        assert c.put("/api/risk/config", json={"vol_filter": True, "min_atr_points": 30, "max_atr_points": 300}).json()["vol_filter"] is True
        c.put("/api/risk/config", json={"vol_filter": False, "min_atr_points": 0, "max_atr_points": 0})
