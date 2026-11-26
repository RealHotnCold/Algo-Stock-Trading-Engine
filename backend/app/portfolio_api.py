from fastapi import APIRouter, HTTPException
from .mt5.gateway import MT5Unavailable
from .portfolio import analytics as an
from .db import Session, Trade
from sqlalchemy import select

router = APIRouter(prefix="/api")

def _g():
    from . import main
    return main.gw, main.exe

def _merge(closed_open, db_rows):
    """Join MT5 round trips with the app's own records (strategy/manual tag, confidence, latency)."""
    rows, used = [], set()
    for t in closed_open:
        m = next((r for r in db_rows if r.ticket is not None and (r.ticket == t["position_id"] or r.ticket in t["orders"])), None)
        if m: used.add(m.id)
        src = m.source if m else ("strategy (no record)" if t.get("magic") == 5151 else "app (no record)" if t.get("magic") == 5150 else "external")
        rows.append(dict(id=f"mt5-{t['position_id']}", symbol=t["symbol"], side=t["side"], volume=t["volume"], entry_price=t["entry_price"], exit_price=t["exit_price"], entry_time=t["entry_time"],
                         exit_time=t["exit_time"], profit=t["profit"], status=t["status"], source=src, confidence=m.confidence if m else None, latency_infer_ms=m.latency_infer_ms if m else None,
                         latency_exec_ms=m.latency_exec_ms if m else None, origin="mt5+app" if m else "mt5"))
    for r in db_rows:
        if r.id in used: continue
        rows.append(dict(id=f"app-{r.id}", symbol=r.symbol, side=r.direction, volume=r.volume, entry_price=r.entry_price, exit_price=r.exit_price, entry_time=r.entry_time, exit_time=r.exit_time,
                         profit=r.profit, status="closed" if r.exit_time else "unconfirmed", source=r.source, confidence=r.confidence, latency_infer_ms=r.latency_infer_ms, latency_exec_ms=r.latency_exec_ms, origin="app only"))
    return sorted(rows, key=lambda x: x["entry_time"] or 0, reverse=True)

def _sync(closed_open, db_rows):
    """Persist real exit data from MT5 into the app's own records, so they survive when MT5 is offline."""
    by = {t["position_id"]: t for t in closed_open}; changed = False
    with Session() as s, s.begin():
        for r in db_rows:
            t = by.get(r.ticket) or next((x for x in closed_open if r.ticket in x["orders"]), None)
            if t and t["status"] == "closed" and r.exit_time is None:
                row = s.get(Trade, r.id); row.exit_price, row.exit_time, row.profit = t["exit_price"], t["exit_time"], t["profit"]
                if t["entry_price"]: row.entry_price = t["entry_price"]
                changed = True
    return changed

@router.get("/trades")
def trades(days: int = 365):
    gw, _ = _g()
    with Session() as s: db_rows = list(s.scalars(select(Trade)).all())
    try: pairs = an.pair_deals(gw.deals(days)); avail = True
    except MT5Unavailable: pairs, avail = [], False
    if avail and _sync(pairs, db_rows):
        with Session() as s: db_rows = list(s.scalars(select(Trade)).all())
    rows = _merge(pairs, db_rows)
    return {"mt5_available": avail, "rows": rows, "stats": an.trade_stats([r for r in rows if r["status"] == "closed"]), "by_source": an.breakdown(rows, "source"), "time_note": "Times are broker server time."}

@router.get("/portfolio")
def portfolio(days: int = 90):
    gw, exe = _g(); st = gw.status()
    if not st["connected"]:
        return {"connected": False, "reason": st.get("reason"), "message": "MT5 is disconnected. Account figures, positions and P&L come only from a connected terminal; nothing is estimated."}
    acc = st["account"]; pos = gw.positions(); deals = gw.deals(max(days, 1)); pairs = an.pair_deals(deals); closed = [t for t in pairs if t["status"] == "closed"]
    specs = {}
    for p in pos:
        try: specs[p["symbol"]] = gw.spec(p["symbol"])
        except MT5Unavailable: pass
    rows, by = [], {}
    for p in pos:
        sp = specs.get(p["symbol"]); sl = p["sl"] or None
        risk = abs(p["price_open"] - sl) / sp["tick_size"] * sp["tick_value"] * p["volume"] if sp and sl else None
        notional = p["volume"] * sp["contract_size"] * p["price_open"] if sp else None
        rows.append({**p, "risk_at_stop": risk, "risk_pct_equity": 100 * risk / acc["equity"] if risk is not None and acc["equity"] else None, "notional": notional})
        e = by.setdefault(p["symbol"], dict(symbol=p["symbol"], long_lots=0.0, short_lots=0.0, risk_at_stop=0.0, unprotected=0, pnl=0.0))
        e["long_lots" if p["side"] == "buy" else "short_lots"] += p["volume"]; e["pnl"] += p["profit"]
        if risk is None: e["unprotected"] += 1
        else: e["risk_at_stop"] += risk
    pts, mdd = an.balance_curve([d for d in deals if d["time"] >= 0], acc["balance"]); unreal = sum(p["profit"] for p in pos)
    peak = max([b for _, b in pts] + [acc["equity"]]); cfg = exe.cfg; total_lots = sum(p["volume"] for p in pos)
    try: daily = gw.daily_pnl()
    except MT5Unavailable: daily = None
    lim_loss = acc["balance"] * cfg.max_daily_loss_pct / 100
    return {"connected": True, "account": acc, "positions": rows, "exposure": list(by.values()), "total_lots": total_lots,
            "pnl": {"unrealized": unreal, "today_realized_plus_floating": daily, "realized_period": sum(t["profit"] for t in closed), "period_days": days},
            "drawdown": {"max_realized_balance_pct": mdd, "current_from_peak_equity_pct": 100 * (peak - acc["equity"]) / peak if peak > 0 else 0.0},
            "balance_curve": [{"time": t, "balance": b} for t, b in pts], "daily_pnl": an.daily_pnl(closed), "stats": an.trade_stats(closed),
            "by_symbol": an.breakdown(closed, "symbol"), "win_loss_hist": an.histogram([t["profit"] for t in closed]),
            "limits": {"open_positions": [len(pos), cfg.max_open_positions], "total_lots": [total_lots, cfg.max_total_lots],
                       "daily_loss": [max(0.0, -daily) if daily is not None else None, lim_loss]}, "time_note": "Times are broker server time."}
