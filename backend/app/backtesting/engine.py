"""Bar-by-bar backtester. Signal formed at the CLOSE of bar i is filled at the OPEN of bar i+1 (no look-ahead).
Costs: half-spread + slippage on every fill. SL/TP checked on bar high/low; if a bar could hit both, SL is assumed first (pessimistic).
Assumes quote currency == account currency (e.g. EURUSD on a USD account) and zero commission."""
from dataclasses import dataclass
import numpy as np

BARS_YR = 252 * 288
BARS_PER_YEAR = {"M5": 252 * 288, "M15": 252 * 96, "H1": 252 * 24}
@dataclass
class BtConfig:
    initial_capital: float = 10000.0; risk_pct: float = 1.0; sl_atr: float = 2.0; tp_atr: float = 3.0
    slippage_pips: float = 0.1; default_spread_pips: float = 1.0; pip: float = 1e-4
    contract_size: float = 100000.0; cooldown_bars: int = 0; bars_yr: float = BARS_YR; max_lots: float = 5.0; min_lots: float = 0.01; lot_step: float = 0.01

def backtest(t, o, h, l, c, atr_bps, spread_pips, decide, lo, hi, cfg: BtConfig):
    eq, pos, lots, entry, sl, tp, ei, cool = cfg.initial_capital, 0, 0.0, 0.0, 0.0, 0.0, 0, -1
    curve = np.full(hi - lo, eq); inpos = np.zeros(hi - lo, bool); trades = []; target = 0

    def close_trade(i, px, why):
        nonlocal eq, pos, lots, cool
        if why == "sl": cool = i + cfg.cooldown_bars          # no re-entry for N bars after a stop-out
        pnl = (px - entry) * pos * lots * cfg.contract_size; eq += pnl
        trades.append(dict(entry_time=int(t[ei]), exit_time=int(t[i]), side="buy" if pos > 0 else "sell", lots=lots,
                           entry=entry, exit=px, sl=sl, tp=tp, pnl=pnl, reason=why)); pos, lots = 0, 0.0

    for i in range(lo, hi):
        sp = spread_pips[i] if spread_pips[i] > 0 else cfg.default_spread_pips
        half = (sp / 2 + cfg.slippage_pips) * cfg.pip
        if i > lo and target != pos:                       # fill pending order at this bar's open
            if pos != 0: close_trade(i, o[i] - half if pos > 0 else o[i] + half, "signal")
            if target != 0 and i >= cool:
                d = cfg.sl_atr * atr_bps[i - 1] * 1e-4 * c[i - 1]
                lt = np.floor(eq * cfg.risk_pct / 100 / (d * cfg.contract_size) / cfg.lot_step) * cfg.lot_step if d > 0 else 0
                lt = min(lt, cfg.max_lots)
                if lt >= cfg.min_lots:
                    pos, lots, ei = target, float(lt), i; entry = o[i] + half if pos > 0 else o[i] - half
                    sl = entry - pos * d; tp = entry + pos * cfg.tp_atr * atr_bps[i - 1] * 1e-4 * c[i - 1]
        if pos != 0:                                       # intrabar exits
            if (pos > 0 and l[i] <= sl) or (pos < 0 and h[i] >= sl): close_trade(i, (min(sl, o[i]) if pos > 0 else max(sl, o[i])) - pos * cfg.slippage_pips * cfg.pip, "sl")  # gaps fill at the open, not the stop
            elif (pos > 0 and h[i] >= tp) or (pos < 0 and l[i] <= tp): close_trade(i, tp - pos * half, "tp")
        if i == hi - 1 and pos != 0: close_trade(i, c[i], "end")
        curve[i - lo] = eq + (pos * (c[i] - entry) * lots * cfg.contract_size if pos != 0 else 0.0); inpos[i - lo] = pos != 0
        target = decide(i, pos) if i < hi - 1 else pos
    return curve, inpos, trades

def metrics(curve, inpos, trades, c_lo, c_hi, cfg):
    r = np.diff(curve) / curve[:-1]; pnl = np.array([x["pnl"] for x in trades]) if trades else np.array([])
    dn = r[r < 0]; peak = np.maximum.accumulate(curve); n = len(curve)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    tot = curve[-1] / cfg.initial_capital - 1
    return dict(total_return_pct=100 * tot, annualized_return_pct=100 * ((1 + tot) ** (cfg.bars_yr / n) - 1) if tot > -1 else -100.0,
                sharpe=float(r.mean() / (r.std() + 1e-12) * np.sqrt(cfg.bars_yr)), sortino=float(r.mean() / (np.sqrt((dn ** 2).mean()) + 1e-12) * np.sqrt(cfg.bars_yr)) if len(dn) else None,
                max_drawdown_pct=float(100 * ((peak - curve) / peak).max()), trades=len(trades),
                win_rate_pct=float(100 * (pnl > 0).mean()) if len(pnl) else None, profit_factor=float(gp / gl) if gl > 0 else None,
                avg_trade=float(pnl.mean()) if len(pnl) else None, exposure_pct=float(100 * inpos.mean()),
                benchmark_buy_hold_pct=100 * (c_hi / c_lo - 1), final_equity=float(curve[-1]))
