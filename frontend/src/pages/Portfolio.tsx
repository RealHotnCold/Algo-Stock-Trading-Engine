import { useEffect, useState } from "react";
import { api } from "../services/api";
import { HBars, HistBars, PnlBars, TimeLine } from "../components/Chart";

const f = (v: number | null | undefined, d = 2, s = "") => (v == null ? "n/a" : v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }) + s);
const cls = (v: number | null | undefined) => (v == null ? "" : v >= 0 ? "up" : "down");
const Kpi = ({ k, v, c }: { k: string; v: string; c?: string }) => <div><span>{k}</span><b className={c}>{v}</b></div>;

export default function Portfolio() {
  const [d, setD] = useState<any>(null), [err, setErr] = useState(""), [days, setDays] = useState(90);
  useEffect(() => { const load = () => api.portfolio(days).then(x => { setD(x); setErr(""); }).catch(e => setErr(e.message)); load(); const i = setInterval(load, 5000); return () => clearInterval(i); }, [days]);
  if (err) return <div className="page doc"><p className="err">{err}</p></div>;
  if (!d) return <div className="page doc"><p className="note">Loading…</p></div>;
  if (!d.connected) return <div className="page doc"><h2>Portfolio &amp; risk</h2><p className="warn">{d.message}{d.reason ? ` (${d.reason})` : ""}</p><p className="note">Open MetaTrader 5, log into your demo account, and this page fills in automatically.</p></div>;
  const a = d.account, cur = a.currency, st = d.stats, L = d.limits;
  const exp = d.exposure.flatMap((e: any) => [e.long_lots > 0 && { label: `${e.symbol} long`, pct: 0, v: e.long_lots, color: "#3fb68b" }, e.short_lots > 0 && { label: `${e.symbol} short`, pct: 0, v: e.short_lots, color: "#e5534b" }].filter(Boolean));
  const mxe = Math.max(...exp.map((x: any) => x.v), 0.0001);
  const use = (u: number | null, lim: number) => (u == null || !lim ? 0 : (100 * u) / lim);
  return (
    <div className="page doc wide">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}><h2 style={{ margin: 0 }}>Portfolio &amp; risk</h2>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>History<select value={days} onChange={e => setDays(+e.target.value)}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select></label></div>
      <p className={`badge ${a.kind === "demo" ? "demo" : "real"}`} style={{ display: "inline-block" }}>{a.kind === "demo" ? "Demo account" : a.kind.toUpperCase() + " account"} · {a.broker} · {a.server} · 1:{a.leverage}</p>
      <div className="kpis">
        <Kpi k="Balance" v={`${f(a.balance)} ${cur}`} /><Kpi k="Equity" v={f(a.equity)} /><Kpi k="Free margin" v={f(a.margin_free)} /><Kpi k="Used margin" v={f(a.margin)} />
        <Kpi k="Margin level" v={a.margin > 0 ? f((100 * a.equity) / a.margin, 0, "%") : "n/a"} /><Kpi k="Open positions" v={String(d.positions.length)} /><Kpi k="Total exposure" v={`${f(d.total_lots)} lots`} />
        <Kpi k="Unrealized P&L" v={f(d.pnl.unrealized)} c={cls(d.pnl.unrealized)} /><Kpi k="Today (realized + floating)" v={f(d.pnl.today_realized_plus_floating)} c={cls(d.pnl.today_realized_plus_floating)} />
        <Kpi k={`Realized, ${d.pnl.period_days}d`} v={f(d.pnl.realized_period)} c={cls(d.pnl.realized_period)} /><Kpi k="Max drawdown (realized balance)" v={f(d.drawdown.max_realized_balance_pct, 1, "%")} /><Kpi k="Current drawdown (from peak equity)" v={f(d.drawdown.current_from_peak_equity_pct, 1, "%")} /></div>
      <h4>Open positions</h4>
      {d.positions.length === 0 ? <p className="note">No open positions.</p> : <div className="scroll"><table><thead><tr><th>Symbol</th><th>Side</th><th>Lots</th><th>Open</th><th>SL</th><th>TP</th><th>P&amp;L</th><th>Risk at stop</th><th>% equity</th></tr></thead><tbody>
        {d.positions.map((p: any) => <tr key={p.ticket}><td>{p.symbol}</td><td className={p.side === "buy" ? "up" : "down"}>{p.side}</td><td>{p.volume}</td><td>{p.price_open}</td><td>{p.sl || "none"}</td><td>{p.tp || "–"}</td><td className={cls(p.profit)}>{f(p.profit)}</td>
          <td>{p.risk_at_stop == null ? <span className="down">no stop-loss</span> : f(p.risk_at_stop)}</td><td>{f(p.risk_pct_equity, 2, "%")}</td></tr>)}</tbody></table></div>}
      <div className="grid2">
        <div><h4>Balance curve (realized, from deal history)</h4>{d.balance_curve.length ? <TimeLine points={d.balance_curve.map((p: any) => ({ time: p.time, value: p.balance }))} /> : <p className="note">No closed deals in this period.</p>}</div>
        <div><h4>Daily realized P&amp;L</h4>{d.daily_pnl.length ? <PnlBars labels={d.daily_pnl.map((x: any) => x.date)} values={d.daily_pnl.map((x: any) => x.pnl)} /> : <p className="note">No closed trades in this period.</p>}</div>
        <div><h4>Exposure by instrument (lots)</h4>{exp.length ? <HBars rows={exp.map((x: any) => ({ label: x.label, pct: (100 * x.v) / mxe, text: f(x.v), color: x.color }))} /> : <p className="note">Flat.</p>}</div>
        <div><h4>Risk at stop, % of equity</h4>{d.exposure.length ? <HBars rows={d.exposure.map((e: any) => ({ label: e.symbol + (e.unprotected ? ` (${e.unprotected} without stop)` : ""), pct: Math.min(100, (100 * (100 * e.risk_at_stop / a.equity)) / 3), text: f((100 * e.risk_at_stop) / a.equity, 2, "%"), color: e.unprotected ? "#e5534b" : "#e0a526" }))} /> : <p className="note">No positions.</p>}<p className="note">Bar full = 3% of equity at risk.</p></div>
        <div><h4>Risk limit usage (from the risk engine settings)</h4><HBars rows={[
          { label: "Open positions", pct: use(L.open_positions[0], L.open_positions[1]), text: `${L.open_positions[0]} / ${L.open_positions[1]}` }, { label: "Total lots", pct: use(L.total_lots[0], L.total_lots[1]), text: `${f(L.total_lots[0])} / ${L.total_lots[1]}` },
          { label: "Daily loss", pct: use(L.daily_loss[0], L.daily_loss[1]), text: L.daily_loss[0] == null ? "n/a" : `${f(L.daily_loss[0])} / ${f(L.daily_loss[1])}`, color: use(L.daily_loss[0], L.daily_loss[1]) > 70 ? "#e5534b" : "#e0a526" }]} /></div>
        <div><h4>Win / loss distribution (closed trades, P&amp;L)</h4>{d.win_loss_hist.counts.length ? <HistBars {...d.win_loss_hist} color="pn" /> : <p className="note">No closed trades.</p>}</div></div>
      <h4>Trade performance, last {d.pnl.period_days} days</h4>
      <div className="kpis"><Kpi k="Closed trades" v={String(st.n)} /><Kpi k="Win rate" v={f(st.win_rate, 0, "%")} /><Kpi k="Profit factor" v={f(st.profit_factor)} /><Kpi k="Avg win" v={f(st.avg_win)} /><Kpi k="Avg loss" v={f(st.avg_loss)} /><Kpi k="Expectancy / trade" v={f(st.expectancy)} c={cls(st.expectancy)} /><Kpi k="Best" v={f(st.best)} /><Kpi k="Worst" v={f(st.worst)} /></div>
      {Object.keys(d.by_symbol).length > 0 && <table className="cmp"><thead><tr><th>Instrument</th><th>Trades</th><th>Win rate</th><th>Net P&amp;L</th></tr></thead><tbody>{Object.entries(d.by_symbol).map(([k, v]: [string, any]) => <tr key={k}><td>{k}</td><td>{v.n}</td><td>{f(v.win_rate, 0, "%")}</td><td className={cls(v.net)}>{f(v.net)}</td></tr>)}</tbody></table>}
      <p className="note">Figures come from MT5 account info, positions and deal history. {d.time_note} Commission and swap are included in P&amp;L. Refreshes every 5 s.</p>
    </div>
  );
}
