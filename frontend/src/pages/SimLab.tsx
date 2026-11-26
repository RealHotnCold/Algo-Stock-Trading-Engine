import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import { loadSettings } from "../services/settings";
import { Chart, HistBars } from "../components/Chart";
import PriceChart, { Marker } from "../components/PriceChart";

const f = (v: number | null | undefined, d = 2, s = "") => (v == null ? "n/a" : v.toFixed(d) + s);
const N = (s: string) => Number(s);
function Field({ l, v, set, w }: { l: string; v: string; set: (s: string) => void; w?: boolean }) { return <label>{l}<input value={v} onChange={e => set(e.target.value)} inputMode="decimal" style={w ? { width: "100%" } : undefined} /></label>; }
function Sel({ l, v, set, opts }: { l: string; v: string; set: (s: string) => void; opts: string[][] }) { return <label>{l}<select value={v} onChange={e => set(e.target.value)}>{opts.map(([a, b]) => <option key={a} value={a}>{b}</option>)}</select></label>; }
const Kpis = ({ rows }: { rows: [string, string][] }) => <div className="kpis">{rows.map(([k, v]) => <div key={k}><span>{k}</span><b>{v}</b></div>)}</div>;
const TFS = [["M5", "M5"], ["M15", "M15"], ["H1", "H1"]];

function MonteCarlo() {
  const [p, setP] = useState({ tf: "M5", method: "bootstrap", drift: "zero", n_sims: "1000", horizon: "1000", capital: "10000", direction: "1", leverage: "10", block: "24", ruin_level: "0.5", lookback_bars: "20000" });
  const [r, setR] = useState<any>(null), [busy, setBusy] = useState(false), [err, setErr] = useState(""); const s = (k: string) => (v: string) => setP(o => ({ ...o, [k]: v }));
  const run = () => { setBusy(true); setErr(""); api.mc({ symbol: "EURUSD", tf: p.tf, method: p.method, drift: p.drift, n_sims: N(p.n_sims), horizon: N(p.horizon), capital: N(p.capital), direction: N(p.direction), leverage: N(p.leverage), block: N(p.block), ruin_level: N(p.ruin_level), lookback_bars: N(p.lookback_bars) }).then(setR).catch(e => setErr(e.message)).finally(() => setBusy(false)); };
  useEffect(() => { loadSettings().then(s => setP(o => ({ ...o, ...Object.fromEntries(Object.entries(s.simulation).map(([k, v]) => [k, String(v)])) }))).catch(() => {}); }, []);
  const m = r?.metrics, cap = N(p.capital);
  return <div>
    <p className="warn">SIMULATION: paths below are synthetic, generated from past returns. They are not forecasts.</p>
    <div className="form">
      <Sel l="Method" v={p.method} set={s("method")} opts={[["bootstrap", "Block bootstrap"], ["gbm", "GBM (normal returns)"], ["strategy_trades", "Resample strategy trades"]]} />
      <Sel l="Timeframe" v={p.tf} set={s("tf")} opts={TFS} /><Sel l="Drift" v={p.drift} set={s("drift")} opts={[["zero", "Zero (neutral)"], ["historical", "Historical"]]} />
      <Field l="History bars used" v={p.lookback_bars} set={s("lookback_bars")} /><Field l="Simulations" v={p.n_sims} set={s("n_sims")} /><Field l="Horizon (bars, or trades)" v={p.horizon} set={s("horizon")} />
      <Field l="Capital" v={p.capital} set={s("capital")} /><Sel l="Position" v={p.direction} set={s("direction")} opts={[["1", "Long"], ["-1", "Short"]]} /><Field l="Leverage (×notional)" v={p.leverage} set={s("leverage")} />
      <Field l="Bootstrap block (bars)" v={p.block} set={s("block")} /><Field l="Ruin level (× capital)" v={p.ruin_level} set={s("ruin_level")} />
      <button className="go buy" disabled={busy} onClick={run}>{busy ? "Simulating…" : "Run simulation"}</button></div>
    {err && <p className="err">{err}</p>}
    {r && m && <>
      <Kpis rows={[["Expected final", f(m.expected_final, 0)], ["Median final", f(m.median_final, 0)], ["5th pct final", f(m.p5_final, 0)], ["95th pct final", f(m.p95_final, 0)], ["P(profit)", f(m.prob_profit * 100, 1, "%")], ["P(loss)", f(m.prob_loss * 100, 1, "%")],
        ["VaR 95%", f(m.var95_pct, 2, "%")], ["CVaR 95%", f(m.cvar95_pct, 2, "%")], ["Median max DD", f(m.median_max_dd_pct, 1, "%")], ["95th pct max DD", f(m.p95_max_dd_pct, 1, "%")], ["Risk of ruin", f(m.risk_of_ruin * 100, 1, "%")]]} />
      <h4>Simulated portfolio value (5–95% and 25–75% bands, median, sample paths)</h4>
      <Chart x={r.x} hline={cap} xLabel={r.info.unit} yLabel="portfolio value" bands={[{ lo: r.bands.p5, hi: r.bands.p95, color: "#e0a526", op: 0.15 }, { lo: r.bands.p25, hi: r.bands.p75, color: "#e0a526", op: 0.3 }]}
        lines={[...r.sample_paths.map((y: number[]) => ({ y, color: "#8b94a3", w: 0.7, op: 0.35 })), { y: r.bands.p50, color: "#e0a526", w: 2 }]} h={300} />
      <div className="grid2"><div><h4>Final return distribution (%)</h4><HistBars {...r.hist_final_return_pct} color="pn" /></div><div><h4>Max drawdown distribution (%)</h4><HistBars {...r.hist_max_dd_pct} color="#e5534b" /></div></div>
      <p className="note">{r.info.source}. {r.info.note}.{r.info.annual_vol != null && ` Annualized volatility in sample: ${(r.info.annual_vol * 100).toFixed(1)}%.`} {r.limitations} Runtime {r.runtime_s}s.</p></>}
  </div>;
}

function BlackScholes() {
  const [p, setP] = useState({ S: "1.1", K: "1.1", days: "30", sigma: "7", r: "4", q: "2", kind: "call" }); const [r, setR] = useState<any>(null), [err, setErr] = useState(""); const s = (k: string) => (v: string) => setP(o => ({ ...o, [k]: v }));
  const run = () => { setErr(""); api.bs({ S: N(p.S), K: N(p.K), days: N(p.days), sigma: N(p.sigma) / 100, r: N(p.r) / 100, q: N(p.q) / 100, kind: p.kind }).then(setR).catch(e => setErr(e.message)); };
  useEffect(run, []);
  const fill = () => api.histVol("EURUSD", "M5").then(h => setP(o => ({ ...o, S: String(h.last_close), K: String(h.last_close), sigma: (h.annual_vol * 100).toFixed(2) }))).catch(e => setErr(e.message));
  const g = r?.greeks;
  return <div>
    <p className="warn">THEORETICAL: prices come from the parameters entered here. MT5 provides no option quotes for this instrument. With a foreign-rate yield (q) this is the Garman-Kohlhagen FX form.</p>
    <div className="form"><Sel l="Type" v={p.kind} set={s("kind")} opts={[["call", "Call"], ["put", "Put"]]} /><Field l="Underlying price" v={p.S} set={s("S")} /><Field l="Strike" v={p.K} set={s("K")} /><Field l="Days to expiry" v={p.days} set={s("days")} />
      <Field l="Volatility (% p.a.)" v={p.sigma} set={s("sigma")} /><Field l="Risk-free rate (%)" v={p.r} set={s("r")} /><Field l="Dividend / foreign rate (%)" v={p.q} set={s("q")} />
      <button className="go buy" onClick={run}>Calculate</button><button onClick={fill}>Fill from EURUSD history</button></div>
    {err && <p className="err">{err}</p>}
    {g && <><Kpis rows={[["Theoretical price", g.price.toPrecision(5)], ["Delta", g.delta.toFixed(4)], ["Gamma", g.gamma.toFixed(4)], ["Theta / day", g.theta.toPrecision(3)], ["Vega / vol pt", g.vega.toPrecision(3)], ["Rho / 1%", g.rho.toPrecision(3)]]} />
      <div className="grid2">
        <div><h4>Value vs underlying (now vs expiry payoff)</h4><Chart x={r.spot.x} xLabel="underlying" yLabel="value" lines={[{ y: r.spot.value, color: "#e0a526", w: 2 }, { y: r.spot.payoff, color: "#8b94a3", dash: "4 3" }]} /></div>
        <div><h4>Delta vs underlying</h4><Chart x={r.spot.x} xLabel="underlying" yLabel="delta" lines={[{ y: r.spot.delta, color: "#3fb68b", w: 2 }]} /></div>
        <div><h4>Gamma vs underlying</h4><Chart x={r.spot.x} xLabel="underlying" yLabel="gamma" lines={[{ y: r.spot.gamma, color: "#e5534b", w: 2 }]} /></div>
        <div><h4>Price vs volatility (%)</h4><Chart x={r.vol.x} xLabel="volatility %" yLabel="price" lines={[{ y: r.vol.value, color: "#e0a526", w: 2 }]} /></div>
        <div><h4>Price vs days to expiry (time decay)</h4><Chart x={r.time.x} xLabel="days to expiry" yLabel="price" lines={[{ y: r.time.value, color: "#e0a526", w: 2 }]} /></div></div>
      <p className="note">{r.note}</p></>}
  </div>;
}

function Replay() {
  const [p, setP] = useState({ tf: "M5", period: "test", offset: "0", n_bars: "300", cooldown_bars: "0" }); const [r, setR] = useState<any>(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const [idx, setIdx] = useState(60), [play, setPlay] = useState(false), [speed, setSpeed] = useState(150); const s = (k: string) => (v: string) => setP(o => ({ ...o, [k]: v }));
  const load = () => { setBusy(true); setErr(""); setPlay(false); api.replay({ symbol: "EURUSD", tf: p.tf, period: p.period, offset: N(p.offset), n_bars: N(p.n_bars), cooldown_bars: N(p.cooldown_bars) }).then(x => { setR(x); setIdx(Math.min(60, x.bars.length)); }).catch(e => setErr(e.message)).finally(() => setBusy(false)); };
  const n = r?.bars.length ?? 0; const tm = useRef<number>();
  useEffect(() => { if (!play) return; tm.current = window.setInterval(() => setIdx(i => { if (i >= n) { setPlay(false); return i; } return i + 1; }), speed); return () => clearInterval(tm.current); }, [play, speed, n]);
  const cur = r ? r.bars[idx - 1] : null; const upto = r ? r.trades.filter((t: any) => t.entry_time <= cur.time) : [];
  const markers: Marker[] = r ? upto.flatMap((t: any) => { const buy = t.side === "buy", out: Marker[] = [{ time: t.entry_time, position: buy ? "belowBar" : "aboveBar", color: buy ? "#3fb68b" : "#e5534b", shape: buy ? "arrowUp" : "arrowDown", text: "in" }];
    if (t.exit_time <= cur.time) out.push({ time: t.exit_time, position: buy ? "aboveBar" : "belowBar", color: t.pnl >= 0 ? "#3fb68b" : "#e5534b", shape: "circle", text: t.reason }); return out; }) : [];
  return <div>
    <p className="note">Replays the trained strategy on stored history. The decision at each bar uses only data up to that bar's close, and orders fill at the next open (no look-ahead). This is a replay of history, not a live feed.</p>
    <div className="form"><Sel l="Timeframe" v={p.tf} set={s("tf")} opts={TFS} /><Sel l="Period" v={p.period} set={s("period")} opts={[["test", "Test (out-of-sample)"], ["val", "Validation"], ["all", "All"]]} /><Field l="Start offset (bars)" v={p.offset} set={s("offset")} /><Field l="Bars to replay" v={p.n_bars} set={s("n_bars")} /><Field l="SL cooldown (bars)" v={p.cooldown_bars} set={s("cooldown_bars")} />
      <button className="go buy" disabled={busy} onClick={load}>{busy ? "Loading…" : "Load replay"}</button></div>
    {err && <p className="err">{err}</p>}
    {r && cur && <>
      <p className={r.out_of_sample ? "ok" : "warn"}>{r.out_of_sample ? "Out-of-sample window." : "In-sample or selection data: not evidence of performance."} {new Date(r.start * 1000).toISOString().slice(0, 16).replace("T", " ")} → {new Date(r.end * 1000).toISOString().slice(0, 16).replace("T", " ")}</p>
      <div className="row player"><button onClick={() => setPlay(!play)}>{play ? "Pause" : "Play"}</button><input type="range" min={5} max={n} value={idx} onChange={e => { setPlay(false); setIdx(N(e.target.value)); }} style={{ flex: 1 }} aria-label="replay position" />
        <select value={speed} onChange={e => setSpeed(N(e.target.value))}><option value={400}>Slow</option><option value={150}>Normal</option><option value={40}>Fast</option></select><span className="note">{idx}/{n}</span></div>
      <div className="replay"><div className="rchart"><PriceChart bars={r.bars.slice(0, idx).map((b: any) => ({ ...b, volume: 0 }))} markers={markers} /></div>
        <aside className="info"><h3>Bar {new Date(cur.time * 1000).toISOString().slice(5, 16).replace("T", " ")}</h3><dl>
          <dt>Regime</dt><dd>{cur.regime}</dd><dt>Decision</dt><dd>{cur.decision}</dd><dt>Confidence</dt><dd>{(cur.confidence * 100).toFixed(0)}%</dd>
          {Object.entries(cur.agents).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd className={v === "buy" ? "up" : v === "sell" ? "down" : ""}>{v as string}</dd></Fragment>)}
          <dt>Equity</dt><dd>{r.equity[idx - 1].toFixed(2)}</dd><dt>Trades so far</dt><dd>{upto.length}</dd></dl></aside></div>
      <div className="scroll"><table><thead><tr><th>Entry</th><th>Side</th><th>Entry px</th><th>SL</th><th>TP</th><th>Exit px</th><th>P&L</th><th>Reason</th></tr></thead><tbody>
        {upto.slice(-12).reverse().map((t: any, i: number) => <tr key={i}><td>{new Date(t.entry_time * 1000).toISOString().slice(5, 16).replace("T", " ")}</td><td className={t.side === "buy" ? "up" : "down"}>{t.side}</td><td>{t.entry.toFixed(5)}</td><td>{t.sl.toFixed(5)}</td><td>{t.tp.toFixed(5)}</td>
          <td>{t.exit_time <= cur.time ? t.exit.toFixed(5) : "open"}</td><td className={t.pnl >= 0 ? "up" : "down"}>{t.exit_time <= cur.time ? t.pnl.toFixed(2) : "–"}</td><td>{t.exit_time <= cur.time ? t.reason : ""}</td></tr>)}</tbody></table></div></>}
  </div>;
}

function Scenario() {
  const [p, setP] = useState({ tf: "M5", period: "test", offset: "0", n_bars: "3000", vol_mult: "2", gap_pct: "0", gap_at_pct: "50", reversal_at_pct: "", spread_mult: "1", extra_slippage_pips: "0", cooldown_bars: "0" });
  const [r, setR] = useState<any>(null), [err, setErr] = useState(""), [busy, setBusy] = useState(false); const s = (k: string) => (v: string) => setP(o => ({ ...o, [k]: v }));
  const run = () => { setBusy(true); setErr(""); api.scenario({ symbol: "EURUSD", tf: p.tf, period: p.period, offset: N(p.offset), n_bars: N(p.n_bars), vol_mult: N(p.vol_mult), gap_pct: N(p.gap_pct), gap_at_pct: N(p.gap_at_pct), reversal_at_pct: p.reversal_at_pct === "" ? null : N(p.reversal_at_pct), spread_mult: N(p.spread_mult), extra_slippage_pips: N(p.extra_slippage_pips), cooldown_bars: N(p.cooldown_bars) }).then(setR).catch(e => setErr(e.message)).finally(() => setBusy(false)); };
  const rows: [string, string, (m: any) => string][] = [["Total return", "total_return_pct", m => f(m.total_return_pct, 1, "%")], ["Max drawdown", "max_drawdown_pct", m => f(m.max_drawdown_pct, 1, "%")], ["Trades", "trades", m => String(m.trades)], ["Exposure", "exposure_pct", m => f(m.exposure_pct, 0, "%")], ["Profit factor", "profit_factor", m => f(m.profit_factor)], ["Sharpe", "sharpe", m => f(m.sharpe)]];
  return <div>
    <p className="warn">WHAT-IF: shocks are applied to a window of real history, then the trained strategy is re-run on the altered data. Results are hypothetical.</p>
    <div className="form"><Sel l="Timeframe" v={p.tf} set={s("tf")} opts={TFS} /><Sel l="Period" v={p.period} set={s("period")} opts={[["test", "Test"], ["val", "Validation"], ["all", "All"]]} /><Field l="Start offset (bars)" v={p.offset} set={s("offset")} /><Field l="Window (bars)" v={p.n_bars} set={s("n_bars")} />
      <Field l="Volatility ×" v={p.vol_mult} set={s("vol_mult")} /><Field l="Price gap (%)" v={p.gap_pct} set={s("gap_pct")} /><Field l="Gap at (% of window)" v={p.gap_at_pct} set={s("gap_at_pct")} /><Field l="Trend reversal at (% of window)" v={p.reversal_at_pct} set={s("reversal_at_pct")} />
      <Field l="Spread ×" v={p.spread_mult} set={s("spread_mult")} /><Field l="Extra slippage (pips)" v={p.extra_slippage_pips} set={s("extra_slippage_pips")} /><Field l="SL cooldown (bars)" v={p.cooldown_bars} set={s("cooldown_bars")} />
      <button className="go buy" disabled={busy} onClick={run}>{busy ? "Running…" : "Run scenario"}</button></div>
    {err && <p className="err">{err}</p>}
    {r && <>
      <table className="cmp"><thead><tr><th /><th>Baseline</th><th>Scenario</th></tr></thead><tbody>{rows.map(([l, , fn]) => <tr key={l}><td>{l}</td><td>{fn(r.baseline.metrics)}</td><td>{fn(r.scenario.metrics)}</td></tr>)}
        <tr><td>Bars in high-vol regime</td><td>{f(r.baseline.high_vol_share * 100, 0, "%")}</td><td>{f(r.scenario.high_vol_share * 100, 0, "%")}</td></tr></tbody></table>
      <h4>Equity curves</h4><Chart x={r.baseline.curve.map((_: number, i: number) => i)} xLabel="sample" yLabel="equity" hline={10000} lines={[{ y: r.baseline.curve, color: "#8b94a3", w: 2 }, { y: r.scenario.curve, color: "#e0a526", w: 2 }]} />
      <p className="note">Grey: baseline. Amber: scenario. {r.note} {r.bars} bars, runtime {r.runtime_s}s.</p></>}
  </div>;
}

export default function SimLab() {
  const TABS = ["Monte Carlo", "Black-Scholes", "Strategy replay", "Market scenarios"]; const [t, setT] = useState(TABS[0]);
  return <div className="page doc wide"><h2>Simulation lab</h2>
    <div className="subtabs">{TABS.map(x => <button key={x} className={x === t ? "on" : ""} onClick={() => setT(x)}>{x}</button>)}</div>
    {t === TABS[0] ? <MonteCarlo /> : t === TABS[1] ? <BlackScholes /> : t === TABS[2] ? <Replay /> : <Scenario />}</div>;
}
