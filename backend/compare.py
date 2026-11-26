"""Train 6 configs (tf x drift-neutral), choose on VALIDATION only, run TEST once for the chosen one."""
import sys, json, pickle, shutil, time, numpy as np, pandas as pd
from app.market_data.history import parse_csv, resample
from app.strategy.meta import Strategy
from app.backtesting.engine import BtConfig, BARS_PER_YEAR
from app.backtesting import runner
df5 = parse_csv(open(sys.argv[1], "rb").read()).reset_index(drop=True); steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
CD = {"M5": 12, "M15": 4, "H1": 1}      # cooldown = ~1 hour after a stop-out
rows, models, out = [], {}, {}
def bt(S, df, tf, period, cd): 
    r = runner.run(S, df, period, BtConfig(cooldown_bars=cd, bars_yr=BARS_PER_YEAR[tf]), None); return r["metrics"]
for tf in ("M5", "M15", "H1"):
    df = df5 if tf == "M5" else resample(df5, tf)
    for dn in (False, True):
        t0 = time.time(); S = Strategy(); S.fit(df, steps=steps, drift_neutral=dn, log=lambda *a: None)
        for cd in (0, CD[tf]):
            m = bt(S, df, tf, "val", cd)
            row = dict(tf=tf, drift_neutral=dn, cooldown_bars=cd, val_return_pct=round(m["total_return_pct"], 1), val_profit_factor=None if m["profit_factor"] is None else round(m["profit_factor"], 2),
                       val_trades=m["trades"], val_sharpe=round(m["sharpe"], 2), val_max_dd_pct=round(m["max_drawdown_pct"], 1), val_buy_hold_pct=round(m["benchmark_buy_hold_pct"], 1))
            rows.append(row); models[(tf, dn, cd)] = (S, df); print(row, flush=True)
        pickle.dump(S, open(f"models/strategy_{tf}{'_dn' if dn else ''}.pkl", "wb"))
ok = [r for r in rows if r["val_trades"] >= 30]; best = max(ok, key=lambda r: r["val_return_pct"])      # selection uses validation only
S, df = models[(best["tf"], best["drift_neutral"], best["cooldown_bars"])]
test = bt(S, df, best["tf"], "test", best["cooldown_bars"]); print("CHOSEN", best); print("TEST (run once)", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in test.items()})
shutil.copy(f"models/strategy_{best['tf']}{'_dn' if best['drift_neutral'] else ''}.pkl", f"models/strategy_{best['tf']}_best.pkl")
json.dump(dict(configs_tried=len(rows), selection="validation total return, >=30 trades", validation=rows, chosen=best, test_of_chosen=test,
               note="Validation is also used for agent gating and the confidence threshold, so validation figures are optimistic. Test was run once, for the chosen config only."), open("models/comparison.json", "w"), indent=1)
