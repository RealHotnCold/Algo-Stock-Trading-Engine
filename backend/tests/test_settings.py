import os; os.environ.setdefault("DB_URL", "sqlite:///./data/test.db")
from fastapi.testclient import TestClient
from app import main
from app.risk.engine import RiskConfig

def test_settings_roundtrip_and_validation():
    with TestClient(main.app) as c:
        d = c.get("/api/settings").json(); assert d["general"]["default_timeframe"] and "risk" not in d
        ind = [{"id": "a1", "type": "SMA", "params": {"period": 50}}, {"id": "b2", "type": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}}]
        r = c.put("/api/settings", json={"chart": {"indicators": ind, "show_grid": False}, "general": {"favourites": ["EURUSD"], "default_timeframe": "M15"}}); assert r.status_code == 200
        d = c.get("/api/settings").json(); assert d["chart"]["indicators"] == ind and d["chart"]["show_grid"] is False and d["general"]["default_timeframe"] == "M15" and d["chart"]["show_volume"] is True
        for bad in ({"chart": {"indicators": [{"id": "x", "type": "EVIL", "params": {}}]}}, {"general": {"default_timeframe": "M7"}}, {"nope": {"a": 1}}, {"strategy": {"risk_pct": 99}}, {"general": {"password": "x"}}, {"chart": {"show_grid": "yes"}}):
            assert c.put("/api/settings", json=bad).status_code == 400, bad
        assert c.get("/api/settings").json()["chart"]["show_grid"] is False                      # failed updates changed nothing

def test_risk_validation_and_persistence():
    with TestClient(main.app) as c:
        assert c.put("/api/risk/config", json={"risk_per_trade_pct": 50}).status_code == 400 and c.put("/api/risk/config", json={"bogus": 1}).status_code == 400
        r = c.put("/api/risk/config", json={"risk_per_trade_pct": 0.5, "max_open_positions": 2, "session_utc_hours": [7, 17]}).json(); assert r["risk_per_trade_pct"] == 0.5
        main.exe.cfg = RiskConfig()                                                              # simulate restart: in-memory reset, then startup restore
        from app import settings_store; saved = settings_store.load_risk(); assert saved.risk_per_trade_pct == 0.5 and saved.session_utc_hours == (7, 17)
        c.put("/api/risk/config", json={"risk_per_trade_pct": 1.0, "max_open_positions": 3, "session_utc_hours": None})

def test_reconnect_when_no_terminal():
    with TestClient(main.app) as c: s = c.post("/api/mt5/reconnect").json(); assert s["connected"] is False and s["trading_allowed"] is False
