import { useEffect, useState } from "react";
import { api } from "../services/api";
import SignalCard from "../components/SignalCard";
import { Chart } from "../components/Chart";

const FLOW = ["Market data", "Features", "Regime (trend × vol)", "4 DDQN agents", "Meta-decision (gating + memory)", "Risk engine", "Order validation", "MT5 demo"];
const COL = ["#8b94a3", "#e0a526", "#6aa8ff", "#3fb68b", "#c792ea", "#e5534b"];
const label = (c: any) => `${c.tf} ${c.drift_neutral ? "improved" : "baseline"}`;
const p1 = (v: number | null | undefined, d = 1, s = "") => (v == null ? "n/a" : v.toFixed(d) + s);
function WalkForward({ wf }: { wf: any }) {
  const ok = wf.configs.filter((c: any) => !c.error), pos = ok.filter((c: any) => c.stitched.total_return_pct > 0).length, sig = ok.filter((c: any) => c.pooled_trades.ci95[0] > 0).length;
  const x = Array.from({ length: 300 }, (_, i) => i / 299);
  return <>
    <h3>Walk-forward evaluation</h3>
    <p className="note">{wf.design} {wf.caveat}</p>
    <p className="warn">{pos} of {ok.length} configurations have a positive stitched out-of-sample return; {sig} have a per-trade profit whose 95% interval sits entirely above zero. All {wf.configs.length} configurations are shown; none was selected afterwards.</p>
    <div className="scroll"><table><thead><tr><th>Config</th><th>Folds +</th><th>Mean fold</th><th>Median fold</th><th>Stitched return</th><th>Buy &amp; hold</th><th>Max DD</th><th>Sharpe</th><th>Trades</th><th>Mean trade P&amp;L (95% CI)</th><th>vs random entry</th></tr></thead><tbody>
      {wf.configs.map((c: any, i: number) => c.error ? <tr key={i}><td>{label(c)}</td><td colSpan={10} className="err">{c.error}</td></tr> : <tr key={i}><td><span style={{ color: COL[i] }}>■</span> {label(c)}</td><td>{c.folds_positive}/{c.n_folds} (p={p1(c.sign_test_p, 2)})</td><td>{p1(c.mean_fold_return_pct, 1, "%")}</td><td>{p1(c.median_fold_return_pct, 1, "%")}</td>
        <td className={c.stitched.total_return_pct >= 0 ? "up" : "down"}>{p1(c.stitched.total_return_pct, 1, "%")}</td><td>{p1(c.buy_hold_stitched_pct, 1, "%")}</td><td>{p1(c.stitched.max_dd_pct, 0, "%")}</td><td>{p1(c.stitched.sharpe, 1)}</td><td>{c.pooled_trades.n}</td>
        <td>{p1(c.pooled_trades.mean_pnl, 2)} [{p1(c.pooled_trades.ci95[0], 1)}, {p1(c.pooled_trades.ci95[1], 1)}]</td><td>{p1(c.mean_excess_vs_random_pct, 1, " pts")}</td></tr>)}</tbody></table></div>
    <h4>Stitched out-of-sample equity (start 10,000; each config on its own folds)</h4>
    <Chart x={x} h={300} hline={10000} xLabel="out-of-sample period (fraction)" yLabel="equity" lines={ok.map((c: any) => ({ y: c.curve, color: COL[wf.configs.indexOf(c)], w: 1.8 }))} />
    <h4>Return per fold, % (random-entry mean in brackets)</h4>
    <div className="scroll"><table><thead><tr><th>Config</th>{ok[0] && ok[0].folds.map((f: any) => <th key={f.fold}>{new Date(f.start * 1000).toISOString().slice(0, 7)}</th>)}</tr></thead><tbody>
      {ok.map((c: any) => <tr key={label(c)}><td>{label(c)}</td>{c.folds.map((f: any) => f.error ? <td key={f.fold} className="err">failed</td> : <td key={f.fold} className={f.return_pct >= 0 ? "up" : "down"}>{p1(f.return_pct, 1)} <span className="note">({p1(f.null_mean_pct, 1)})</span></td>)}</tr>)}</tbody></table></div>
    <p className="note">Each fold retrains agents, scaler, regimes, gating and threshold from scratch on earlier data and is scored on its final 20% only. Fold labels show each test window's start month. Runtime {Math.round(wf.runtime_s / 60)} min.</p>
  </>;
}

export default function Research() {
  const [r, setR] = useState<any>(null); const [err, setErr] = useState(""); const [cmp, setCmp] = useState<any>(null); const [wf, setWf] = useState<any>(null);
  useEffect(() => { api.results().then(setR).catch(e => setErr(e.message)); api.comparison().then(setCmp).catch(() => {}); api.walkforward().then(setWf).catch(() => {}); }, []);
  const tbl = (rows: Record<string, any>) => <table><thead><tr><th /><th>Net bps</th><th>Sharpe</th><th>Max DD bps</th><th>Trades</th><th>Exposure</th></tr></thead><tbody>
    {Object.entries(rows).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.total_bps}</td><td>{v.sharpe}</td><td>{v.max_dd_bps}</td><td>{v.trades ?? "–"}</td><td>{v.exposure ?? "–"}</td></tr>)}</tbody></table>;
  return (
    <div className="page doc">
      <h2>Research strategy</h2>
      <p>A MacroHFT-inspired adaptation, not a reproduction. MacroHFT (Zong et al., KDD 2024) trains several DDQN sub-agents on market segments split by trend and volatility, conditions them on market context via hypernetworks, and mixes them with a memory-augmented hyper-agent. It was built for second/minute-level crypto and futures data.</p>
      <div className="flow">{FLOW.map((f, i) => <span key={f}>{f}{i < FLOW.length - 1 && <i>→</i>}</span>)}</div>
      <table><thead><tr><th>MacroHFT</th><th>This project</th></tr></thead><tbody>
        <tr><td>Trend/volatility decomposition</td><td>3×3 grid: slope t-stat (|t|&gt;2) × realized-vol terciles fitted on training data</td></tr>
        <tr><td>Context-conditioned sub-agents (hypernetworks)</td><td>4 NumPy DDQN agents on regime slices; regime one-hot as input (no hypernetwork)</td></tr>
        <tr><td>Memory-augmented hyper-agent (trained RL)</td><td>Regime gating from validation performance + kNN memory of recent outcomes (not trained end-to-end)</td></tr>
        <tr><td>HFT data</td><td>EURUSD M5, chronological 60/20/20 split</td></tr></tbody></table>
      <h3>Results on stored EURUSD M5 data</h3>
      {err ? <p className="note">{err}</p> : !r ? <p className="note">Loading…</p> : <>
        <p className="note">Splits: train {r.splits.train}; validation {r.splits.val}; test {r.splits.test}. Cost assumed {r.cost_bps_assumed} bps per position change (not measured).</p>
        <h4>Test (untouched)</h4>{tbl(r.test)}<h4>Validation (used for selection, optimistic)</h4>{tbl(r.val)}
        <p className="warn">The system shows no demonstrated edge. On the test period the meta-system lost roughly what the market moved. The volatility agent's gain came from being short in a falling market and was not selected on validation. Do not read these as evidence of profitability.</p></>}
      {cmp && <><h3>Improvement attempt: timeframe × drift-neutral × stop-out cooldown</h3>
        <p className="note">{cmp.configs_tried} configurations were tried and chosen on validation only ({cmp.selection}). {cmp.note}</p>
        <table><thead><tr><th>TF</th><th>Drift-neutral</th><th>Cooldown</th><th>Val return %</th><th>PF</th><th>Trades</th><th>Sharpe</th><th>Max DD %</th></tr></thead><tbody>
          {cmp.validation.map((v: any, i: number) => <tr key={i} className={v.tf === cmp.chosen.tf && v.drift_neutral === cmp.chosen.drift_neutral && v.cooldown_bars === cmp.chosen.cooldown_bars ? "pick" : ""}><td>{v.tf}</td><td>{v.drift_neutral ? "yes" : "no"}</td><td>{v.cooldown_bars}</td><td>{v.val_return_pct}</td><td>{v.val_profit_factor ?? "–"}</td><td>{v.val_trades}</td><td>{v.val_sharpe}</td><td>{v.val_max_dd_pct}</td></tr>)}</tbody></table>
        <p>Chosen config on the untouched test period (run once): return {cmp.test_of_chosen.total_return_pct.toFixed(1)}%, profit factor {cmp.test_of_chosen.profit_factor?.toFixed(2) ?? "n/a"}, {cmp.test_of_chosen.trades} trades, max drawdown {cmp.test_of_chosen.max_drawdown_pct.toFixed(1)}%, buy &amp; hold {cmp.test_of_chosen.benchmark_buy_hold_pct.toFixed(1)}%.</p></>}
      {wf && <WalkForward wf={wf} />}
      <h3>Live decision</h3><SignalCard symbol="EURUSD" full />
    </div>
  );
}
