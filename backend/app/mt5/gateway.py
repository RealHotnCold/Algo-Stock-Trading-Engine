"""MT5 access behind one interface. Never fabricates data: if the terminal is
unavailable calls raise MT5Unavailable and the API reports 'disconnected'."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .. import config

class MT5Unavailable(RuntimeError): pass

TF_NAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]
TRADE_MODE = {0: "demo", 1: "contest", 2: "real"}

def account_kind(trade_mode: int) -> str:
    return TRADE_MODE.get(trade_mode, "unknown")

def trading_allowed(kind: str, demo_only: bool | None = None, allow_real: bool | None = None) -> tuple[bool, str]:
    """Guard run before ANY order. Real accounts need explicit opt-in."""
    demo_only = config.DEMO_ONLY if demo_only is None else demo_only
    allow_real = config.ALLOW_REAL_TRADING if allow_real is None else allow_real
    if kind == "demo": return True, "demo account"
    if kind == "real" and not demo_only and allow_real: return True, "real account explicitly enabled"
    if kind == "real": return False, "blocked: real account while demo-only mode is on"
    return False, f"blocked: unrecognised account type '{kind}'"

@dataclass
class AccountInfo:
    login: int; server: str; broker: str; currency: str; kind: str
    balance: float; equity: float; margin: float; margin_free: float; leverage: int

class MT5Gateway:
    def __init__(self): self._mt5: Any = None

    def _lib(self):
        if self._mt5 is None:
            try: import MetaTrader5 as mt5  # Windows only
            except ImportError as e:
                raise MT5Unavailable("MetaTrader5 package not installed (Windows only)") from e
            self._mt5 = mt5
        return self._mt5

    def connect(self) -> bool:
        mt5 = self._lib()
        kw = {k: v for k, v in dict(path=config.MT5_PATH, login=config.MT5_LOGIN,
              password=config.MT5_PASSWORD, server=config.MT5_SERVER).items() if v}
        if not mt5.initialize(**kw): raise MT5Unavailable(f"initialize failed: {mt5.last_error()}")
        return True

    def status(self) -> dict:
        try:
            mt5 = self._lib(); self.connect()
            term, acc = mt5.terminal_info(), mt5.account_info()
            if term is None or acc is None: raise MT5Unavailable("terminal has no logged-in account")
            kind = account_kind(acc.trade_mode); ok, why = trading_allowed(kind)
            return {"connected": True, "terminal_connected": bool(term.connected),
                    "account": asdict(AccountInfo(acc.login, acc.server, acc.company, acc.currency, kind,
                        acc.balance, acc.equity, acc.margin, acc.margin_free, acc.leverage)),
                    "demo_only": config.DEMO_ONLY, "trading_allowed": ok, "trading_reason": why}
        except MT5Unavailable as e:
            return {"connected": False, "reason": str(e), "demo_only": config.DEMO_ONLY,
                    "trading_allowed": False, "trading_reason": "disconnected"}

    def symbols(self) -> list[dict]:
        mt5 = self._lib(); self.connect()
        return [{"name": s.name, "description": s.description, "path": s.path, "digits": s.digits}
                for s in (mt5.symbols_get() or []) if s.visible]

    def tick(self, symbol: str) -> dict:
        mt5 = self._lib(); self.connect()
        t, info = mt5.symbol_info_tick(symbol), mt5.symbol_info(symbol)
        if t is None or info is None: raise MT5Unavailable(f"no tick for {symbol}")
        return {"symbol": symbol, "bid": t.bid, "ask": t.ask, "last": t.last,
                "spread_points": info.spread, "time": t.time, "digits": info.digits,
                "market_open": info.trade_mode != 0}

    def bars(self, symbol: str, tf: str, count: int = 1000) -> list[dict]:
        mt5 = self._lib(); self.connect()
        tfc = getattr(mt5, f"TIMEFRAME_{tf}", None)
        if tfc is None: raise ValueError(f"unsupported timeframe {tf}")
        mt5.symbol_select(symbol, True)
        r = mt5.copy_rates_from_pos(symbol, tfc, 0, count)
        if r is None or len(r) == 0: raise MT5Unavailable(f"no bars for {symbol} {tf}")
        return [{"time": int(x["time"]), "open": float(x["open"]), "high": float(x["high"]),
                 "low": float(x["low"]), "close": float(x["close"]),
                 "volume": float(x["tick_volume"])} for x in r]

# ---- Phase 2: trading methods (UNTESTED against a live terminal; see tests/fake gateway) ----
def pick_filling(mask: int) -> str:
    """symbol_info.filling_mode bitmask: 1=FOK, 2=IOC. Otherwise RETURN."""
    return "FOK" if mask & 1 else "IOC" if mask & 2 else "RETURN"

DONE_CODES = {10009: "done", 10008: "placed"}

def _spec(self, symbol: str) -> dict:
    mt5 = self._lib(); self.connect(); i = mt5.symbol_info(symbol)
    if i is None: raise MT5Unavailable(f"unknown symbol {symbol}")
    return {"symbol": symbol, "digits": i.digits, "point": i.point, "tick_size": i.trade_tick_size,
            "tick_value": i.trade_tick_value, "contract_size": i.trade_contract_size,
            "vol_min": i.volume_min, "vol_max": i.volume_max, "vol_step": i.volume_step,
            "filling": pick_filling(i.filling_mode), "stops_level": i.trade_stops_level}

def _positions(self) -> list[dict]:
    mt5 = self._lib(); self.connect()
    return [{"ticket": p.ticket, "symbol": p.symbol, "side": "buy" if p.type == 0 else "sell", "volume": p.volume,
             "price_open": p.price_open, "sl": p.sl, "tp": p.tp, "profit": p.profit, "time": p.time, "magic": p.magic}
            for p in (mt5.positions_get() or [])]

def _daily_pnl(self) -> float:
    import datetime as dt
    mt5 = self._lib(); self.connect()
    start = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(start, dt.datetime.now() + dt.timedelta(days=1)) or []
    realized = sum(d.profit + d.commission + d.swap for d in deals)
    return realized + sum(p.profit for p in (mt5.positions_get() or []))

def _request(self, o: dict, spec: dict) -> dict:
    mt5 = self._lib(); t = self.tick(o["symbol"]); buy = o["side"] == "buy"
    pending = o.get("order_type", "market") != "market"
    act = {"market": mt5.TRADE_ACTION_DEAL}.get(o.get("order_type", "market"), mt5.TRADE_ACTION_PENDING)
    kind = {("market", True): mt5.ORDER_TYPE_BUY, ("market", False): mt5.ORDER_TYPE_SELL,
            ("limit", True): mt5.ORDER_TYPE_BUY_LIMIT, ("limit", False): mt5.ORDER_TYPE_SELL_LIMIT,
            ("stop", True): mt5.ORDER_TYPE_BUY_STOP, ("stop", False): mt5.ORDER_TYPE_SELL_STOP}[(o.get("order_type", "market"), buy)]
    fill = {"FOK": mt5.ORDER_FILLING_FOK, "IOC": mt5.ORDER_FILLING_IOC, "RETURN": mt5.ORDER_FILLING_RETURN}[spec["filling"]]
    return {"action": act, "symbol": o["symbol"], "volume": o["volume"], "type": kind,
            "price": o["price"] if pending else (t["ask"] if buy else t["bid"]),
            "sl": o.get("sl") or 0.0, "tp": o.get("tp") or 0.0, "deviation": o.get("deviation", 20),
            "magic": o.get("magic", 5150), "comment": o.get("comment", "terminal")[:30],
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": fill}

def _wrap(r):
    """order_check results have no order/deal/price/volume fields, order_send results do: read defensively."""
    if r is None: return {"retcode": -1, "comment": "no result from MT5"}
    g = lambda k, d=0: getattr(r, k, d)
    return {"retcode": r.retcode, "comment": getattr(r, "comment", ""), "order": g("order"), "deal": g("deal"), "price": g("price", 0.0), "volume": g("volume", 0.0),
            "margin": g("margin", None), "margin_free": g("margin_free", None)}

def _check(self, o, spec): return _wrap(self._lib().order_check(self._request(o, spec)))
def _send(self, o, spec): return _wrap(self._lib().order_send(self._request(o, spec)))
def _close(self, ticket: int) -> dict:
    mt5 = self._lib(); self.connect(); p = next((x for x in (mt5.positions_get(ticket=ticket) or [])), None)
    if p is None: return {"retcode": -1, "comment": "position not found"}
    t = self.tick(p.symbol); spec = self.spec(p.symbol); buy = p.type == 0
    req = {"action": mt5.TRADE_ACTION_DEAL, "position": ticket, "symbol": p.symbol, "volume": p.volume,
           "type": mt5.ORDER_TYPE_SELL if buy else mt5.ORDER_TYPE_BUY, "price": t["bid"] if buy else t["ask"],
           "deviation": 20, "magic": 5150, "comment": "close", "type_time": mt5.ORDER_TIME_GTC,
           "type_filling": {"FOK": mt5.ORDER_FILLING_FOK, "IOC": mt5.ORDER_FILLING_IOC, "RETURN": mt5.ORDER_FILLING_RETURN}[spec["filling"]]}
    return _wrap(mt5.order_send(req))

MT5Gateway.spec, MT5Gateway.positions, MT5Gateway.daily_pnl = _spec, _positions, _daily_pnl
MT5Gateway.order_check, MT5Gateway.order_send, MT5Gateway.close_position, MT5Gateway._request = _check, _send, _close, _request

# ---- Phase 6: deal history (UNTESTED against a live terminal) ----
def _deals(self, days: int = 365) -> list[dict]:
    import datetime as dt
    mt5 = self._lib(); self.connect(); now = dt.datetime.now()
    r = mt5.history_deals_get(now - dt.timedelta(days=days + 2), now + dt.timedelta(days=2))   # generous range: MT5 datetime/timezone handling is quirky
    return [dict(ticket=d.ticket, order=d.order, time=int(d.time), type=d.type, entry=d.entry, position_id=d.position_id, volume=d.volume, price=d.price,
                 commission=d.commission, swap=d.swap, profit=d.profit, symbol=d.symbol, magic=d.magic, comment=d.comment) for d in (r or [])]
MT5Gateway.deals = _deals
