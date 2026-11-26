import numpy as np
from app.backtesting.engine import backtest, metrics, BtConfig

def bars(n=200, drift=2e-5):
    c = 1.1 + np.arange(n) * drift; o = c - drift / 2
    return np.arange(n) * 300, o, c + 1e-5, c - 1e-5, c, np.full(n, 3.0), np.full(n, 1.0)

def test_fill_at_next_open_with_costs_and_profit_in_uptrend():
    t, o, h, l, c, atr, sp = bars(); cfg = BtConfig(tp_atr=50, sl_atr=50)
    curve, inpos, trades = backtest(t, o, h, l, c, atr, sp, lambda i, pos: 1, 0, 200, cfg)
    assert abs(trades[0]["entry"] - (o[1] + (0.5 + 0.1) * 1e-4)) < 1e-12      # entry = next bar open + half spread + slippage
    assert curve[-1] > cfg.initial_capital and len(curve) == 200

def test_stop_loss_hit_loses_about_risk_pct():
    t, o, h, l, c, atr, sp = bars(); l2 = l.copy(); l2[50] = 1.0       # bar 50 trades far below the stop, open unchanged
    cfg = BtConfig(risk_pct=1.0, sl_atr=2.0, tp_atr=50)
    _, _, trades = backtest(t, o, h, l2, c, atr, sp, lambda i, pos: 1, 0, 200, cfg)
    sl_tr = [x for x in trades if x["reason"] == "sl"]
    assert sl_tr and -1.5 * 100 < sl_tr[0]["pnl"] < -0.9 * 100

def test_gap_through_stop_fills_at_open():
    t, o, h, l, c, atr, sp = bars(); o2, l2 = o.copy(), l.copy(); o2[50] = 1.0; l2[50] = 1.0
    _, _, trades = backtest(t, o2, h, l2, c, atr, sp, lambda i, pos: 1, 0, 200, BtConfig(tp_atr=50))
    assert trades[0]["reason"] == "sl" and trades[0]["exit"] < 1.0 + 1e-3

def test_higher_spread_hurts():
    t, o, h, l, c, atr, sp = bars(); cfg = BtConfig(tp_atr=50, sl_atr=50); flip = lambda i, pos: 1 if i % 2 == 0 else -1
    a = backtest(t, o, h, l, c, atr, np.full(200, 0.5), flip, 0, 200, cfg)[0][-1]
    b = backtest(t, o, h, l, c, atr, np.full(200, 3.0), flip, 0, 200, cfg)[0][-1]
    assert b < a

def test_metrics_keys():
    t, o, h, l, c, atr, sp = bars(); cfg = BtConfig(); r = backtest(t, o, h, l, c, atr, sp, lambda i, pos: 1, 0, 200, cfg)
    m = metrics(*r, c[0], c[-1], cfg); assert m["trades"] >= 1 and m["max_drawdown_pct"] >= 0

def test_cooldown_blocks_reentry_after_stop():
    t, o, h, l, c, atr, sp = bars(); l2 = l.copy(); l2[50] = 1.0
    for cd, expect in ((0, 51), (10, 60)):
        _, _, tr = backtest(t, o, h, l2, c, atr, sp, lambda i, pos: 1, 0, 200, BtConfig(tp_atr=50, cooldown_bars=cd))
        assert tr[0]["reason"] == "sl" and tr[1]["entry_time"] == t[expect]

def test_resample_m5_to_m15():
    import pandas as pd
    from app.market_data.history import resample
    d = pd.DataFrame(dict(time=np.arange(6) * 300, open=[1, 2, 3, 4, 5, 6.], high=[2, 3, 9, 5, 6, 7.], low=[0, 1, 2, 3, 4, 5.], close=[1.5, 2.5, 3.5, 4.5, 5.5, 6.5], volume=[1.] * 6, spread=[0, 10, 20, 0, 0, 0.]))
    r = resample(d, "M15"); assert len(r) == 2 and r.open[0] == 1 and r.high[0] == 9 and r.low[0] == 0 and r.close[0] == 3.5 and r.volume[0] == 3 and r.spread[0] == 15 and r.spread[1] == 0
