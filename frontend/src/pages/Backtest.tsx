import { useEffect, useRef, useState } from "react";
import { createChart, UTCTimestamp } from "lightweight-charts";
import { api, BtResult } from "../services/api";
import { loadSettings } from "../services/settings";

const f = (v: number | null | undefined, d = 2, suf = "") => (v == null ? "n/a" : v.toFixed(d) + suf);
const day = (t: number) => new Date(t * 1000).toISOString().slice(0, 10);

function Equity({ curve }: { curve: BtResult["curve"] }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const c = createChart(el.current!, { autoSize: true, layout: { background: { color: "#14171c" }, textColor: "#8b94a3", fontFamily: "IBM Plex Mono" },
      grid: { vertLines: { color: "#1d222a" }, horzLines: { color: "#1d222a" } }, rightPriceScale: { borderColor: "#2a303a" }, timeScale: { borderColor: "#2a303a", timeVisible: true } });
    c.addLineSeries({ color: "#e0a526", lineWidth: 2 }).setData(curve.map(p => ({ time: p.time as UTCTimestamp, value: p.equity })));
    c.timeScale().fitContent(); return () => c.remove();
  }, [curve]);
  return <div ref={el} className="eq" />;
}

function Hist({ pnl }: { pnl: number[] }) {
  if (!pnl.length) return null;
  const lo = Math.min(...pnl), hi = Math.max(...pnl), n = 24, w = (hi - lo) / n || 1, bins = Array(n).fill(0);
  pnl.forEach(v => bins[Math.min(n - 1, Math.floor((v - lo) / w))]++); const mx = Math.max(...bins);
  return <svg viewBox="0 0 480 110" className="hist" role="img" aria-label="Trade P&L distribution">
    {bins.map((b, i) => <rect key={i} x={i * 20 + 1} y={90 - (b / mx) * 85} width={18} height={(b / mx) * 85} fill={lo + (i + .5) * w >= 0 ? "#3fb68b" : "#e5534b"} />)}
    <text x="0" y="106" fill="#8b94a3" fontSize="10">{lo.toFixed(0)}</text><text x="480" y="106" fill="#8b94a3" fontSize="10" textAnchor="end">{hi.toFixed(0)}</text></svg>;
}

export default function Backtest() {
  useEffect(() => { loadSettings().then(s => setP(o => ({ ...o, ...s.strategy }))).catch(() => {}); }, []);
  const [p, setP] = useState({ tf: "M5", cooldown_bars: 0, period: "test", initial_capital: 10000, risk_pct: 1, sl_atr: 2, tp_atr: 3, slippage_pips: 0.1, spread_pips: "" });
  const [r, setR] = useState<BtResult | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const set = (k: string, v: string) => setP(o => ({ ...o, [k]: k === "period" ? v : v }) as typeof p);
  const run = () => { setBusy(true); setErr(""); api.backtest({ ...p, initial_capital: +p.initial_capital, risk_pct: +p.risk_pct, sl_atr: +p.sl_atr, tp_atr: +p.tp_atr, slippage_pips: +p.slippage_pips, cooldown_bars: +p.cooldown_bars, spread_pips: p.spread_pips === "" ? null : +p.spread_pips }).then(setR).catch(e => setErr(e.message)).finally(() => setBusy(false)); };
  const m = r?.metrics;
  return (
    <div className="page doc wide">
      <h2>Backtesting</h2>
      <p className="note">Replays the trained strategy bar by bar on stored EURUSD M5 data. Signals form at a bar's close and fill at the next open, with spread and slippage on every fill.</p>
      <div className="form">
        <label>Timeframe<select value={p.tf} onChange={e => set("tf", e.target.value)}><option>M5</option><option>M15</option><option>H1</option></select></label>
        <label>Period<select value={p.period} onChange={e => set("period", e.target.value)}><option value="test">Test (out-of-sample)</option><option value="val">Validation</option><option value="all">All (includes training)</option></select></label>
        {([["initial_capital", "Capital"], ["risk_pct", "Risk %/trade"], ["sl_atr", "SL (×ATR)"], ["tp_atr", "TP (×ATR)"], ["slippage_pips", "Slippage (pips)"], ["cooldown_bars", "SL cooldown (bars)"], ["spread_pips", "Spread override (pips)"]] as const).map(([k, l]) =>
          <label key={k}>{l}<input value={String(p[k])} onChange={e => set(k, e.target.value)} inputMode="decimal" placeholder={k === "spread_pips" ? "use stored" : ""} /></label>)}
        <button className="go buy" disabled={busy} onClick={run}>{busy ? "Running…" : "Run backtest"}</button>
      </div>
      {err && <p className="err">{err}</p>}
      {r && m && <>
        <p className={r.out_of_sample ? "ok" : "warn"}>{r.out_of_sample ? "Out-of-sample period: not used for training or selection." : "In-sample or selection data: results are optimistic and not evidence of performance."}
          {" "}{day(r.start)} → {day(r.end)} · {r.bars.toLocaleString()} bars · {r.runtime_s}s</p>
        <div className="kpis">{([["Total return", f(m.total_return_pct, 1, "%")], ["Buy & hold", f(m.benchmark_buy_hold_pct, 1, "%")], ["Annualized", f(m.annualized_return_pct, 0, "%")], ["Sharpe", f(m.sharpe)], ["Sortino", f(m.sortino)],
          ["Max drawdown", f(m.max_drawdown_pct, 1, "%")], ["Trades", String(m.trades)], ["Win rate", f(m.win_rate_pct, 0, "%")], ["Profit factor", f(m.profit_factor)], ["Avg trade", f(m.avg_trade)], ["Exposure", f(m.exposure_pct, 0, "%")], ["Final equity", f(m.final_equity, 0)]] as const)
          .map(([k, v]) => <div key={k}><span>{k}</span><b>{v}</b></div>)}</div>
        <h4>Equity curve</h4><Equity curve={r.curve} />
        <h4>Trade P&L distribution (last {r.trades.length} of {r.n_trades_total})</h4><Hist pnl={r.trades.map(t => t.pnl)} />
        <h4>Recent trades</h4>
        <div className="scroll"><table><thead><tr><th>Entry</th><th>Exit</th><th>Side</th><th>Lots</th><th>Entry px</th><th>Exit px</th><th>P&L</th><th>Reason</th></tr></thead><tbody>
          {r.trades.slice(-40).reverse().map((t, i) => <tr key={i}><td>{new Date(t.entry_time * 1000).toISOString().slice(0, 16).replace("T", " ")}</td><td>{new Date(t.exit_time * 1000).toISOString().slice(0, 16).replace("T", " ")}</td>
            <td className={t.side === "buy" ? "up" : "down"}>{t.side}</td><td>{t.lots}</td><td>{t.entry.toFixed(5)}</td><td>{t.exit.toFixed(5)}</td><td className={t.pnl >= 0 ? "up" : "down"}>{t.pnl.toFixed(2)}</td><td>{t.reason}</td></tr>)}</tbody></table></div>
        <p className="note">Spreads: {r.spread_source}. {r.assumptions}.</p></>}
    </div>
  );
}
