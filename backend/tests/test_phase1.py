import os; os.environ["DB_URL"] = "sqlite:///./data/test.db"
from fastapi.testclient import TestClient
from app.main import app
from app.mt5.gateway import trading_allowed, account_kind

CSV = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\n2024.01.02\t00:00:00\t1.10\t1.12\t1.09\t1.11\t100\n2024.01.02\t00:05:00\t1.11\t1.13\t1.10\t1.12\t90\n"

def test_guard():
    assert trading_allowed("demo", True, False)[0]
    assert not trading_allowed("real", True, True)[0]    # demo-only wins
    assert not trading_allowed("real", False, False)[0]  # needs explicit opt-in
    assert trading_allowed("real", False, True)[0]
    assert not trading_allowed("unknown")[0]
    assert account_kind(0) == "demo" and account_kind(2) == "real"

def test_api_disconnected_and_import():
    with TestClient(app) as c:
        s = c.get("/api/status").json()
        assert s["connected"] is False and s["trading_allowed"] is False
        assert c.get("/api/tick", params={"symbol": "EURUSD"}).status_code == 503
        assert c.get("/api/bars", params={"symbol": "NOPE", "tf": "M5"}).status_code == 404
        r = c.post("/api/data/import", params={"symbol": "EURUSD", "tf": "M5"}, files={"file": ("x.csv", CSV)})
        assert r.json()["imported"] == 2
        b = c.get("/api/bars", params={"symbol": "EURUSD", "tf": "M5"}).json()
        assert b["source"] == "stored" and len(b["bars"]) == 2
        bad = CSV.replace("1.12\t1.09", "1.00\t1.09")
        assert c.post("/api/data/import", params={"symbol": "X", "tf": "M5"}, files={"file": ("x.csv", bad)}).status_code == 400
