"""Pure analytics over MT5 deal history. Nothing here invents data."""
import datetime as dt

def _vwap(ds): v = sum(d["volume"] for d in ds); return sum(d["price"] * d["volume"] for d in ds) / v if v else None

def pair_deals(deals):
    """Group deals by position into round trips. DEAL_TYPE 0/1 = buy/sell; DEAL_ENTRY 0/2 = in, 1/3 = out."""
    by = {}
    for d in sorted(deals, key=lambda x: (x["time"], x["ticket"])):
        if d["type"] in (0, 1) and d.get("symbol"): by.setdefault(d["position_id"], []).append(d)
    out = []
    for pid, ds in by.items():
        ins = [d for d in ds if d["entry"] in (0, 2)]; outs = [d for d in ds if d["entry"] in (1, 3)]
        side = ("buy" if ins[0]["type"] == 0 else "sell") if ins else ("sell" if outs[0]["type"] == 1 else "buy")   # exit of a buy is a sell
        vin, vout = sum(d["volume"] for d in ins), sum(d["volume"] for d in outs); closed = bool(outs) and vout >= vin - 1e-9
        out.append(dict(position_id=pid, orders=sorted({d["order"] for d in ds}), symbol=ds[0]["symbol"], side=side, volume=vin or vout, entry_price=_vwap(ins), exit_price=_vwap(outs),
                        entry_time=ins[0]["time"] if ins else None, exit_time=outs[-1]["time"] if closed else None, magic=ds[0].get("magic", 0), comment=ds[0].get("comment", ""),
                        profit=sum(d["profit"] + d["commission"] + d["swap"] for d in ds), status="closed" if closed else "open"))
    return sorted(out, key=lambda t: t["entry_time"] or t["exit_time"] or 0)

def trade_stats(trades):
    c = [t["profit"] for t in trades if t["status"] == "closed"]; w = [x for x in c if x > 0]; l = [x for x in c if x < 0]; gp, gl = sum(w), -sum(l)
    return dict(n=len(c), wins=len(w), losses=len(l), win_rate=100 * len(w) / len(c) if c else None, profit_factor=gp / gl if gl > 0 else None, avg_win=gp / len(w) if w else None,
                avg_loss=-gl / len(l) if l else None, expectancy=sum(c) / len(c) if c else None, best=max(c) if c else None, worst=min(c) if c else None, net=sum(c))

def breakdown(trades, key):
    g = {}
    for t in trades:
        if t["status"] == "closed": g.setdefault(t[key], []).append(t)
    return {k: trade_stats(v) for k, v in sorted(g.items())}

def balance_curve(deals, balance_now):
    """Realized balance over time, anchored so the last point equals the current balance."""
    ev = sorted((d for d in deals if d["profit"] + d["commission"] + d["swap"] != 0), key=lambda d: (d["time"], d["ticket"]))
    if not ev: return [], 0.0
    start = balance_now - sum(d["profit"] + d["commission"] + d["swap"] for d in ev); bal, pts = start, [(ev[0]["time"] - 1, start)]
    for d in ev: bal += d["profit"] + d["commission"] + d["swap"]; pts.append((d["time"], bal))
    peak, mdd = pts[0][1], 0.0
    for _, b in pts: peak = max(peak, b); mdd = max(mdd, (peak - b) / peak if peak > 0 else 0)
    return pts, mdd * 100

def daily_pnl(trades):
    g = {}
    for t in trades:
        if t["status"] == "closed" and t["exit_time"]: g[dt.datetime.fromtimestamp(t["exit_time"], dt.timezone.utc).strftime("%Y-%m-%d")] = g.get(dt.datetime.fromtimestamp(t["exit_time"], dt.timezone.utc).strftime("%Y-%m-%d"), 0) + t["profit"]
    return [dict(date=k, pnl=v) for k, v in sorted(g.items())]

def histogram(vals, bins=24):
    if not vals: return {"counts": [], "edges": []}
    import numpy as np
    c, e = np.histogram(vals, bins=bins); return {"counts": c.tolist(), "edges": [float(x) for x in e]}
