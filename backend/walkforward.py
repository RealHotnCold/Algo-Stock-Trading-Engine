"""python walkforward.py <M5 csv> [--steps 3000] [--jobs 1]   -> models/walkforward.json
Each finished configuration is saved to models/wf_part_<i>.json; re-running resumes and skips finished ones (delete the parts to start over).
About 20 min single-process; use --jobs 6 on a many-core machine."""
import os
for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"): os.environ.setdefault(k, "1")
import argparse, json, time
from concurrent.futures import ProcessPoolExecutor
from app.walkforward import CONFIGS, run_config, N_NULL

def part(i): return f"models/wf_part_{i}.json"
def job(csv, i, steps):
    if not os.path.exists(part(i)):
        t0 = time.time(); r = run_config(csv, i, steps); r["runtime_s"] = round(time.time() - t0); json.dump(r, open(part(i), "w")); print("config", i, "done in", r["runtime_s"], "s", flush=True)
    return json.load(open(part(i)))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--steps", type=int, default=3000); ap.add_argument("--jobs", type=int, default=1); a = ap.parse_args(); t0 = time.time()
    n = len(CONFIGS)
    if a.jobs > 1:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex: res = list(ex.map(job, [a.csv] * n, range(n), [a.steps] * n))
    else: res = [job(a.csv, i, a.steps) for i in range(n)]
    json.dump(dict(configs=res, steps=a.steps, null_runs_per_fold=N_NULL, runtime_s=sum(r.get("runtime_s", 0) for r in res),
                   design="Pre-specified 6 configurations (3 timeframes x baseline/improved); ALL reported, none selected. 50% rolling window, step = one test window (10% of data), test = final 20% of each window, every fold retrains from scratch.",
                   caveat="Settings such as training steps, SL/TP multiples and the 0.55 bps cost were chosen earlier on this same dataset, so a little design leakage remains. Random baseline: random-entry policy with roughly matched trade frequency, same costs, stops and cooldown, 20 runs per fold."),
              open("models/walkforward.json", "w"), indent=1)
    print("done", round(time.time() - t0), "s", flush=True)
