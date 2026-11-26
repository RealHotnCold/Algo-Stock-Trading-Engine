"""python train.py <M5 csv> [--tf M5|M15|H1] [--steps 3000] [--dn]   (M15/H1 are resampled from the M5 file)"""
import argparse, pickle, pandas as pd
from app.market_data.history import parse_csv, resample
from app.strategy.meta import Strategy
ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--tf", default="M5"); ap.add_argument("--steps", type=int, default=3000); ap.add_argument("--dn", action="store_true")
a = ap.parse_args(); df = parse_csv(open(a.csv, "rb").read()).reset_index(drop=True)
if a.tf != "M5": df = resample(df, a.tf)
S = Strategy(); S.fit(df, steps=a.steps, drift_neutral=a.dn)
ts = pd.to_datetime(df.time, unit="s")
for k, (lo, hi) in S.split.items(): print(f"{k}: {ts[lo]:%Y-%m-%d} -> {ts[hi-1]:%Y-%m-%d} ({hi-lo} bars)")
path = f"models/strategy_{a.tf}{'_dn' if a.dn else ''}.pkl"; pickle.dump(S, open(path, "wb")); print("saved", path)
