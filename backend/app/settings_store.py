"""User configuration in SQLite. Whitelisted keys only, validated; secrets (MT5 credentials) are never stored here."""
import copy, json
from sqlalchemy import select
from .db import Session, Setting
from .risk.engine import RiskConfig

TFS = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]
IND_TYPES = {"SMA", "EMA", "BB", "VWAP", "VOLMA", "RSI", "MACD", "ATR", "OBV"}
DEFAULTS = {"general": {"default_symbol": "", "default_timeframe": "M5", "favourites": []},
            "chart": {"show_volume": True, "show_grid": True, "indicators": []},
            "notifications": {"connection_changes": True, "order_results": True},
            "strategy": {"risk_pct": 1.0, "sl_atr": 2.0, "tp_atr": 3.0, "slippage_pips": 0.1, "cooldown_bars": 0},
            "simulation": {"capital": 10000, "n_sims": 1000, "horizon": 1000, "leverage": 10, "block": 24}}

def _n(lo, hi): return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi
def _b(v): return isinstance(v, bool)
def _strs(v): return isinstance(v, list) and len(v) <= 50 and all(isinstance(x, str) and 0 < len(x) <= 32 for x in v)
def _inds(v):
    return isinstance(v, list) and len(v) <= 12 and all(isinstance(i, dict) and isinstance(i.get("id"), str) and i.get("type") in IND_TYPES and isinstance(i.get("params"), dict)
                                                       and len(i["params"]) <= 4 and all(_n(1, 1000)(x) for x in i["params"].values()) for i in v)
RULES = {"general": {"default_symbol": lambda v: isinstance(v, str) and len(v) <= 32, "default_timeframe": lambda v: v in TFS, "favourites": _strs},
         "chart": {"show_volume": _b, "show_grid": _b, "indicators": _inds}, "notifications": {"connection_changes": _b, "order_results": _b},
         "strategy": {"risk_pct": _n(0.01, 10), "sl_atr": _n(0.1, 20), "tp_atr": _n(0.1, 50), "slippage_pips": _n(0, 20), "cooldown_bars": _n(0, 1000)},
         "simulation": {"capital": _n(100, 1e9), "n_sims": _n(10, 10000), "horizon": _n(5, 5000), "leverage": _n(0.1, 500), "block": _n(1, 500)}}

def load() -> dict:
    out = copy.deepcopy(DEFAULTS)
    with Session() as s: rows = s.scalars(select(Setting)).all()
    for r in rows:
        if "." in r.key:
            sec, k = r.key.split(".", 1)
            if sec in out and k in out[sec]:
                try: out[sec][k] = json.loads(r.value)
                except ValueError: pass
    return out

def update(partial: dict) -> dict:
    if not isinstance(partial, dict): raise ValueError("expected an object")
    items = []
    for sec, kv in partial.items():
        if sec not in RULES or not isinstance(kv, dict): raise ValueError(f"unknown section '{sec}'")
        for k, v in kv.items():
            if k not in RULES[sec]: raise ValueError(f"unknown setting '{sec}.{k}'")
            if not RULES[sec][k](v): raise ValueError(f"invalid value for '{sec}.{k}'")
            items.append((f"{sec}.{k}", json.dumps(v)))
    with Session() as s, s.begin():
        for k, v in items:
            row = s.get(Setting, k)
            if row: row.value = v
            else: s.add(Setting(key=k, value=v))
    return load()

RISK_RULES = {"risk_per_trade_pct": _n(0.01, 10), "max_daily_loss_pct": _n(0.1, 50), "max_open_positions": _n(1, 50), "max_lots_per_symbol": _n(0.01, 100), "max_total_lots": _n(0.01, 500),
              "vol_filter": _b, "min_atr_points": _n(0, 100000), "max_atr_points": _n(0, 100000), "require_stop_loss": _b, "min_reward_risk": _n(0, 20), "max_spread_points": _n(0, 1000),
              "session_utc_hours": lambda v: v is None or (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, int) and 0 <= x <= 24 for x in v))}

def clean_risk(d: dict) -> dict:
    for k, v in d.items():
        if k not in RISK_RULES: raise ValueError(f"unknown risk setting '{k}'")
        if not RISK_RULES[k](v): raise ValueError(f"invalid value for '{k}'")
    return {k: (tuple(v) if k == "session_utc_hours" and v else v) for k, v in d.items()}

def load_risk() -> RiskConfig | None:
    with Session() as s: row = s.get(Setting, "risk")
    try: return RiskConfig(**clean_risk(json.loads(row.value))) if row else None
    except (ValueError, TypeError): return None

def save_risk(cfg: RiskConfig):
    with Session() as s, s.begin():
        v = json.dumps({**cfg.__dict__, "session_utc_hours": list(cfg.session_utc_hours) if cfg.session_utc_hours else None}); row = s.get(Setting, "risk")
        if row: row.value = v
        else: s.add(Setting(key="risk", value=v))

# ---- chart drawings and price alerts, stored per symbol + timeframe ----
import re
DRAW_TYPES = {"hline", "support", "resistance", "trend", "alert"}
def _fin(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e12

def clean_drawings(items) -> list:
    if not isinstance(items, list) or len(items) > 100: raise ValueError("drawings must be a list of at most 100 items")
    out = []
    for d in items:
        if not isinstance(d, dict) or d.get("type") not in DRAW_TYPES or not isinstance(d.get("id"), str) or not 0 < len(d["id"]) <= 16: raise ValueError("bad drawing")
        t = d["type"]; c = {"id": d["id"], "type": t}
        if t == "trend":
            if not all(_fin(d.get(k)) for k in ("t1", "p1", "t2", "p2")): raise ValueError("trend line needs t1, p1, t2, p2")
            c.update({k: d[k] for k in ("t1", "p1", "t2", "p2")})
        else:
            if not _fin(d.get("price")) or d["price"] <= 0: raise ValueError("price must be a positive number")
            c["price"] = d["price"]
            if t == "alert":
                if d.get("dir") not in ("above", "below"): raise ValueError("alert dir must be above or below")
                c.update(dir=d["dir"], triggered=bool(d.get("triggered", False)))
        out.append(c)
    return out

def _dkey(symbol: str, tf: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._#-]{1,32}", symbol or "") or tf not in TFS: raise ValueError("bad symbol or timeframe")
    return f"drawings:{symbol}:{tf}"

def load_drawings(symbol: str, tf: str) -> list:
    with Session() as s: row = s.get(Setting, _dkey(symbol, tf))
    try: return clean_drawings(json.loads(row.value)) if row else []
    except ValueError: return []

def save_drawings(symbol: str, tf: str, items) -> list:
    items = clean_drawings(items); key = _dkey(symbol, tf)
    with Session() as s, s.begin():
        row = s.get(Setting, key)
        if row: row.value = json.dumps(items)
        else: s.add(Setting(key=key, value=json.dumps(items)))
    return items
