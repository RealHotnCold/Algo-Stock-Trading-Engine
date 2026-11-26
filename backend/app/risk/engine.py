"""Risk engine: separate from strategy, can veto any signal. Every check reports pass/fail + reason."""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict

@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_open_positions: int = 3
    max_lots_per_symbol: float = 1.0
    max_total_lots: float = 2.0
    require_stop_loss: bool = True
    min_reward_risk: float = 1.0       # applies only when a TP is set
    max_spread_points: float = 30
    session_utc_hours: tuple[int, int] | None = None   # (start, end) inclusive start, exclusive end; None = always
    vol_filter: bool = False           # ATR(14) on M5 bars, in broker points; max 0 = no upper cap
    min_atr_points: float = 0
    max_atr_points: float = 0

def size_by_risk(equity: float, risk_pct: float, entry: float, sl: float, spec: dict) -> float:
    dist = abs(entry - sl)
    if dist <= 0 or spec["tick_size"] <= 0 or spec["tick_value"] <= 0: return 0.0
    loss_per_lot = dist / spec["tick_size"] * spec["tick_value"]
    lots = equity * risk_pct / 100 / loss_per_lot
    lots = math.floor(lots / spec["vol_step"] + 1e-9) * spec["vol_step"]
    return round(min(lots, spec["vol_max"]), 8) if lots >= spec["vol_min"] else 0.0

def atr_points(bars: list[dict], spec: dict, n: int = 14) -> float | None:
    """Wilder ATR of the given bars, expressed in broker points."""
    if len(bars) < n + 1 or not spec.get("point"): return None
    tr = [max(b["high"] - b["low"], abs(b["high"] - p["close"]), abs(b["low"] - p["close"])) for p, b in zip(bars, bars[1:])]
    a = sum(tr[:n]) / n
    for x in tr[n:]: a = (a * (n - 1) + x) / n
    return a / spec["point"]

def evaluate(cfg: RiskConfig, o: dict, *, account: dict, positions: list[dict], spec: dict,
             tick: dict, daily_pnl: float, utc_hour: int, atr_points: float | None = None) -> dict:
    checks = []
    def add(name, ok, detail): checks.append({"name": name, "passed": bool(ok), "detail": detail})
    buy = o["side"] == "buy"; entry = o.get("price") or (tick["ask"] if buy else tick["bid"])
    sl, tp, vol = o.get("sl"), o.get("tp"), o["volume"]

    add("stop_loss_present", bool(sl) or not cfg.require_stop_loss, "stop-loss set" if sl else "stop-loss required")
    if sl:
        side_ok = sl < entry if buy else sl > entry
        add("stop_loss_side", side_ok, "SL on correct side of entry" if side_ok else "SL on wrong side of entry")
        risk_amt = abs(entry - sl) / spec["tick_size"] * spec["tick_value"] * vol
        cap = account["equity"] * cfg.risk_per_trade_pct / 100
        add("risk_per_trade", risk_amt <= cap * 1.001, f"risk {risk_amt:.2f} vs cap {cap:.2f} {account['currency']}")
    if tp and sl:
        rr = abs(tp - entry) / abs(entry - sl) if entry != sl else 0
        add("reward_risk", rr >= cfg.min_reward_risk, f"R:R {rr:.2f} (min {cfg.min_reward_risk})")
    add("volume_limits", spec["vol_min"] <= vol <= spec["vol_max"] and abs(vol / spec["vol_step"] - round(vol / spec["vol_step"])) < 1e-6,
        f"volume {vol} (min {spec['vol_min']}, max {spec['vol_max']}, step {spec['vol_step']})")
    add("daily_loss", daily_pnl > -account["balance"] * cfg.max_daily_loss_pct / 100,
        f"daily P&L {daily_pnl:.2f} vs limit -{account['balance'] * cfg.max_daily_loss_pct / 100:.2f}")
    add("open_positions", len(positions) < cfg.max_open_positions, f"{len(positions)} open (max {cfg.max_open_positions})")
    sym_lots = sum(p["volume"] for p in positions if p["symbol"] == o["symbol"])
    add("symbol_exposure", sym_lots + vol <= cfg.max_lots_per_symbol + 1e-9, f"{sym_lots + vol:.2f} lots (max {cfg.max_lots_per_symbol})")
    tot = sum(p["volume"] for p in positions)
    add("total_exposure", tot + vol <= cfg.max_total_lots + 1e-9, f"{tot + vol:.2f} lots (max {cfg.max_total_lots})")
    add("spread", tick["spread_points"] <= cfg.max_spread_points, f"spread {tick['spread_points']} pts (max {cfg.max_spread_points})")
    if cfg.vol_filter:
        if atr_points is None: add("volatility", False, "ATR unavailable (needs recent M5 bars), so the volatility filter cannot pass")
        else:
            ok = atr_points >= cfg.min_atr_points and (cfg.max_atr_points <= 0 or atr_points <= cfg.max_atr_points)
            add("volatility", ok, f"ATR(14, M5) {atr_points:.0f} pts (allowed {cfg.min_atr_points:g} to {'no cap' if cfg.max_atr_points <= 0 else format(cfg.max_atr_points, 'g')})")
    if cfg.session_utc_hours:
        a, b = cfg.session_utc_hours; ok = a <= utc_hour < b if a < b else (utc_hour >= a or utc_hour < b)
        add("session", ok, f"hour {utc_hour} UTC, allowed {a}-{b}")
    return {"approved": all(c["passed"] for c in checks), "checks": checks, "config": asdict(cfg)}
