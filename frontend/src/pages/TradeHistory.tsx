import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";

const ts = (t: number | null) => (t ? new Date(t * 1000).toISOString().slice(0, 16).replace("T", " ") : "–");
const px = (v: number | null) => (v == null ? "–" : v.toFixed(5));
type Row = any;
const COLS: [string, string, (r: Row) => string][] = [["symbol", "Symbol", r => r.symbol], ["side", "Side", r => r.side], ["volume", "Lots", r => String(r.volume)], ["entry_price", "Entry px", r => px(r.entry_price)], ["exit_price", "Exit px", r => px(r.exit_price)],
  ["entry_time", "Entry time", r => ts(r.entry_time)], ["exit_time", "Exit time", r => ts(r.exit_time)], ["profit", "P&L", r => (r.profit == null ? "–" : r.profit.toFixed(2))], ["source", "Source", r => r.source], ["confidence", "Signal conf.", r => (r.confidence == null ? "–" : (r.confidence * 100).toFixed(0) + "%")],
  ["latency_infer_ms", "Infer ms", r => (r.latency_infer_ms == null ? "–" : r.latency_infer_ms.toFixed(0))], ["latency_exec_ms", "MT5 ms", r => (r.latency_exec_ms == null ? "–" : r.latency_exec_ms.toFixed(0))], ["status", "Status", r => r.status]];

export default function TradeHistory() {
  const [data, setData] = useState<any>(null), [err, setErr] = useState("");
  const [q, setQ] = useState(""), [sym, setSym] = useState(""), [side, setSide] = useState(""), [src, setSrc] = useState(""), [status, setStatus] = useState(""), [from, setFrom] = useState(""), [to, setTo] = useState("");
  const [sort, setSort] = useState<{ k: string; asc: boolean }>({ k: "entry_time", asc: false });
  useEffect(() => { const load = () => api.trades().then(x => { setData(x); setErr(""); }).catch(e => setErr(e.message)); load(); const i = setInterval(load, 10000); return () => clearInterval(i); }, []);
  const rows: Row[] = useMemo(() => {
    if (!data) return [];
    const a = from ? new Date(from).getTime() / 1000 : -Infinity, b = to ? new Date(to).getTime() / 1000 + 86400 : Infinity, needle = q.trim().toLowerCase();
    return data.rows.filter((r: Row) => (!sym || r.symbol === sym) && (!side || r.side === side) && (!src || r.source === src) && (!status || r.status === status) && (r.entry_time ?? 0) >= a && (r.entry_time ?? 0) <= b
      && (!needle || [r.symbol, r.side, r.source, r.status, r.origin].join(" ").toLowerCase().includes(needle))).sort((x: Row, y: Row) => {
      const u = x[sort.k], v = y[sort.k]; if (u == null && v == null) return 0; if (u == null) return 1; if (v == null) return -1; return (u < v ? -1 : u > v ? 1 : 0) * (sort.asc ? 1 : -1); });
  }, [data, q, sym, side, src, status, from, to, sort]);
  const symbols: string[] = useMemo(() => (data ? Array.from(new Set<string>(data.rows.map((r: Row) => r.symbol))) : []), [data]);
  const sources: string[] = useMemo(() => (data ? Array.from(new Set<string>(data.rows.map((r: Row) => r.source))) : []), [data]);
  const bySrc = useMemo(() => { const g: Record<string, Row[]> = {}; rows.forEach(r => (g[r.source] ??= []).push(r)); return Object.entries(g).map(([k, v]) => { const c = v.filter(r => r.status === "closed"), avg = (xs: number[]) => (xs.length ? xs.reduce((s, y) => s + y, 0) / xs.length : null);
    return { k, n: v.length, closed: c.length, net: c.reduce((s, r) => s + r.profit, 0), win: c.length ? (100 * c.filter(r => r.profit > 0).length) / c.length : null, conf: avg(v.filter(r => r.confidence != null).map(r => r.confidence)), exec: avg(v.filter(r => r.latency_exec_ms != null).map(r => r.latency_exec_ms)) }; }); }, [rows]);
  const exportCsv = () => {
    const esc = (s: string) => `"${s.replace(/"/g, '""')}"`, head = COLS.map(c => c[1]).concat(["Origin"]).join(","), body = rows.map(r => COLS.map(c => esc(c[2](r))).concat([esc(r.origin)]).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([head + "\n" + body], { type: "text/csv" })), a = document.createElement("a"); a.href = url; a.download = "trade_history.csv"; a.click(); URL.revokeObjectURL(url);
  };
  if (err) return <div className="page doc"><p className="err">{err}</p></div>;
  if (!data) return <div className="page doc"><p className="note">Loading…</p></div>;
  const closed = rows.filter(r => r.status === "closed"), net = closed.reduce((s, r) => s + r.profit, 0);
  return (
    <div className="page doc wide">
      <h2>Trade history</h2>
      {!data.mt5_available && <p className="warn">MT5 is disconnected. Showing only trades recorded by this app. Prices and P&amp;L for trades closed since the last connection are unknown until MT5 reconnects.</p>}
      <div className="filters">
        <input placeholder="Search symbol, side, source…" value={q} onChange={e => setQ(e.target.value)} aria-label="search" />
        <select value={sym} onChange={e => setSym(e.target.value)} aria-label="symbol"><option value="">All symbols</option>{symbols.map(s => <option key={s}>{s}</option>)}</select>
        <select value={side} onChange={e => setSide(e.target.value)} aria-label="side"><option value="">Buy &amp; sell</option><option>buy</option><option>sell</option></select>
        <select value={src} onChange={e => setSrc(e.target.value)} aria-label="source"><option value="">All sources</option>{sources.map(s => <option key={s}>{s}</option>)}</select>
        <select value={status} onChange={e => setStatus(e.target.value)} aria-label="status"><option value="">Any status</option><option>closed</option><option>open</option><option>unconfirmed</option></select>
        <label>From<input type="date" value={from} onChange={e => setFrom(e.target.value)} /></label><label>To<input type="date" value={to} onChange={e => setTo(e.target.value)} /></label>
        <button onClick={exportCsv} disabled={!rows.length}>Export CSV</button></div>
      <p className="note">{rows.length} trades shown · {closed.length} closed · net P&amp;L {net.toFixed(2)} · win rate {closed.length ? ((100 * closed.filter(r => r.profit > 0).length) / closed.length).toFixed(0) + "%" : "n/a"} · {data.time_note}</p>
      <div className="scroll tall"><table><thead><tr>{COLS.map(([k, l]) => <th key={k} className="sortable" onClick={() => setSort(s => ({ k, asc: s.k === k ? !s.asc : true }))}>{l}{sort.k === k ? (sort.asc ? " ▲" : " ▼") : ""}</th>)}</tr></thead><tbody>
        {rows.map(r => <tr key={r.id} className={r.status === "unconfirmed" ? "dim" : ""}>{COLS.map(([k, , fn]) => <td key={k} className={k === "profit" && r.profit != null ? (r.profit >= 0 ? "up" : "down") : k === "side" ? (r.side === "buy" ? "up" : "down") : ""}>{fn(r)}</td>)}</tr>)}
        {!rows.length && <tr><td colSpan={COLS.length} className="note">No trades match. Trades appear here after you place orders from the terminal or trade in MT5.</td></tr>}</tbody></table></div>
      <h4>Strategy vs manual vs external (filtered rows)</h4>
      <table className="cmp"><thead><tr><th>Source</th><th>Trades</th><th>Closed</th><th>Win rate</th><th>Net P&amp;L</th><th>Avg signal conf.</th><th>Avg MT5 ms</th></tr></thead><tbody>
        {bySrc.map(s => <tr key={s.k}><td>{s.k}</td><td>{s.n}</td><td>{s.closed}</td><td>{s.win == null ? "–" : s.win.toFixed(0) + "%"}</td><td className={s.net >= 0 ? "up" : "down"}>{s.net.toFixed(2)}</td><td>{s.conf == null ? "–" : (s.conf * 100).toFixed(0) + "%"}</td><td>{s.exec == null ? "–" : s.exec.toFixed(0)}</td></tr>)}</tbody></table>
      <p className="note">"app only" rows exist in this app's database but not in MT5 history. "external" trades were made directly in the MT5 terminal. Strategy-tagged trades appear once automatic execution is wired up.</p>
    </div>
  );
}
