import { useEffect, useRef, useState } from "react";
import { api, openTicks, Bar, Tick, Drawing } from "../services/api";
import PriceChart from "../components/PriceChart";
import OrderPanel from "../components/OrderPanel";
import Positions from "../components/Positions";
import SignalCard from "../components/SignalCard";
import AutoTrader from "../components/AutoTrader";
import type { Status } from "../services/api";
import IndicatorPanel from "../components/IndicatorPanel";
import type { Ind } from "../utils/indicators";
import { cached, loadSettings, saveSettings } from "../services/settings";

export default function Terminal({ status, notify }: { status: Status | null; notify?: (m: string, k?: "ok" | "err") => void }) {
  const [rk, setRk] = useState(0); const [inds, setInds] = useState<Ind[]>([]); const [open, setOpen] = useState(false); const [prefs, setPrefs] = useState({ show_volume: true, show_grid: true }); const tm = useRef<number>();
  const changeInds = (v: Ind[]) => { setInds(v); window.clearTimeout(tm.current); tm.current = window.setTimeout(() => saveSettings({ chart: { indicators: v } }).catch(() => {}), 600); };
  const [tfs, setTfs] = useState<string[]>([]); const [tf, setTf] = useState("M5");
  const [symbols, setSymbols] = useState<{ name: string }[]>([]); const [symbol, setSymbol] = useState("");
  const [src, setSrc] = useState<"mt5" | "stored">("stored");
  const [bars, setBars] = useState<Bar[]>([]); const [err, setErr] = useState(""); const [tick, setTick] = useState<Tick | null>(null);

  useEffect(() => {
    Promise.all([api.timeframes(), api.symbols(), loadSettings().catch(() => null)]).then(([t, r, s]) => {
      setTfs(t); setSrc(r.source); const fav: string[] = s?.general.favourites ?? [], names = r.symbols.map(x => x.name);
      setSymbols([...r.symbols.filter(x => fav.includes(x.name)), ...r.symbols.filter(x => !fav.includes(x.name))]);
      const ds = s?.general.default_symbol; setSymbol(ds && names.includes(ds) ? ds : fav.find(f => names.includes(f)) ?? names[0] ?? "");
      if (s) { if (t.includes(s.general.default_timeframe)) setTf(s.general.default_timeframe); setInds(s.chart.indicators); setPrefs({ show_volume: s.chart.show_volume, show_grid: s.chart.show_grid }); }
    });
  }, []);
  useEffect(() => {
    if (!symbol) return; setErr("");
    api.bars(symbol, tf).then(r => { setBars(r.bars); setSrc(r.source); }).catch(e => { setBars([]); setErr(e.message); });
  }, [symbol, tf]);
  useEffect(() => { setTick(null); return symbol ? openTicks(symbol, setTick) : undefined; }, [symbol]);

  const t = tick && tick.ok ? tick : null;
  const first = bars[0], lastBar = bars[bars.length - 1];
  const chg = lastBar && first ? lastBar.close - first.open : 0, pct = first ? (chg / first.open) * 100 : 0;
  const d = t?.digits ?? 5;
  const hi = bars.length ? Math.max(...bars.slice(-288).map(b => b.high)) : null, lo = bars.length ? Math.min(...bars.slice(-288).map(b => b.low)) : null;

  const [drawings, setDrawings] = useState<Drawing[]>([]); const [tool, setTool] = useState("none"); const [pending, setPending] = useState<{ time: number; price: number } | null>(null); const [dopen, setDopen] = useState(false); const dtm = useRef<number>();
  useEffect(() => { setTool("none"); setPending(null); if (!symbol) return; let live = true; api.drawings(symbol, tf).then(r => live && setDrawings(r.items)).catch(() => live && setDrawings([])); return () => { live = false; }; }, [symbol, tf]);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === "Escape") { setTool("none"); setPending(null); } }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, []);
  const changeDrawings = (next: Drawing[]) => { setDrawings(next); window.clearTimeout(dtm.current); dtm.current = window.setTimeout(() => api.saveDrawings(symbol, tf, next).catch(() => {}), 500); };
  const nid = () => Math.random().toString(36).slice(2, 10);
  const onChartClick = (p: { time: number; price: number }) => {
    const price = Number(p.price.toFixed(d));
    if (tool === "hline" || tool === "support" || tool === "resistance") { changeDrawings([...drawings, { id: nid(), type: tool as "hline" | "support" | "resistance", price }]); setTool("none"); }
    else if (tool === "alert") { const ref = t?.bid ?? lastBar?.close ?? price; changeDrawings([...drawings, { id: nid(), type: "alert", price, dir: price > ref ? "above" : "below", triggered: false }]); setTool("none"); }
    else if (tool === "trend") { if (!pending) setPending({ time: p.time, price }); else if (p.time !== pending.time) { changeDrawings([...drawings, { id: nid(), type: "trend", t1: pending.time, p1: pending.price, t2: p.time, p2: price }]); setPending(null); setTool("none"); } }
  };
  useEffect(() => {   // price alerts: evaluated against live MT5 bid while this page is open
    if (!t) return; const hit = drawings.filter(x => x.type === "alert" && !x.triggered && (x.dir === "above" ? t.bid >= (x.price as number) : t.bid <= (x.price as number))); if (!hit.length) return;
    hit.forEach(x => notify?.(`${symbol}: price crossed ${x.dir} ${x.price} (bid ${t.bid.toFixed(d)})`, "ok")); changeDrawings(drawings.map(x => (hit.includes(x) ? { ...x, triggered: true } : x)));
  }, [tick]);

  return (
    <div className="terminal">
      <div className="toolbar">
        <select value={symbol} onChange={e => setSymbol(e.target.value)}>{symbols.map(s => <option key={s.name}>{s.name}</option>)}</select>
        <div className="tfs">{tfs.map(x => <button key={x} className={x === tf ? "on" : ""} onClick={() => setTf(x)}>{x}</button>)}</div>
        <span className="indwrap"><button className={inds.length ? "on" : ""} onClick={() => setOpen(!open)} aria-expanded={open}>Indicators{inds.length ? ` (${inds.length})` : ""}</button>{open && <IndicatorPanel inds={inds} onChange={changeInds} />}</span>
        <div className="tfs tools" role="group" aria-label="drawing tools">{[["none", "Cursor"], ["hline", "H-line"], ["trend", "Trend"], ["support", "Support"], ["resistance", "Resistance"], ["alert", "Alert"]].map(([k, l]) => <button key={k} className={tool === k ? "on" : ""} onClick={() => { setTool(k); setPending(null); }}>{l}</button>)}</div>
        <span className="indwrap"><button className={drawings.length ? "on" : ""} onClick={() => setDopen(!dopen)} aria-expanded={dopen}>Drawings ({drawings.length})</button>{dopen && <div className="indpanel" role="dialog" aria-label="Drawings and alerts">
          {drawings.length === 0 && <p className="note">Nothing drawn on {symbol} {tf}. Drawings are saved per symbol and timeframe.</p>}
          {drawings.map(x => <div key={x.id} className="indrow"><b>{x.type}</b><span>{x.type === "trend" ? `${x.p1} → ${x.p2}` : x.price}</span>{x.type === "alert" && <span className="note">{x.triggered ? "triggered" : `when ${x.dir}`}</span>}<button onClick={() => changeDrawings(drawings.filter(y => y.id !== x.id))} aria-label={`delete ${x.type}`}>✕</button></div>)}
          {drawings.length > 0 && <button onClick={() => changeDrawings([])}>Clear all</button>}
          <p className="note">Alerts fire only while this page is open and MT5 is streaming quotes for this symbol.</p></div>}</span>
        {tool !== "none" && <span className="note">{tool === "trend" ? (pending ? "Click the end point" : "Click the start point") : `Click the chart to place a ${tool === "hline" ? "horizontal line" : tool}`} · Esc to cancel</span>}
        <span className={`src ${src}`}>{src === "mt5" ? "MT5 live data" : "Stored history · not live"}</span>
      </div>
      <div className="main">
        <div className="chartwrap">
          {err && <div className="empty">{err}. Import a CSV via <code>POST /api/data/import</code> or connect MT5.</div>}
          {!symbols.length && !err && <div className="empty">No instruments yet. Connect MT5 or import historical data.</div>}
          <PriceChart bars={bars} drawings={drawings} onChartClick={onChartClick} tool={tool} markers={pending ? [{ time: pending.time, position: "aboveBar", color: "#6aa8ff", shape: "circle", text: "start" }] : undefined} indicators={inds} showVolume={prefs.show_volume} showGrid={prefs.show_grid} live={t && src === "mt5" ? { price: t.bid, time: t.time } : null} />
        </div>
        <aside className="info">
          <h3>{symbol || "—"}</h3>
          <dl>
            <dt>Bid</dt><dd>{t ? t.bid.toFixed(d) : "n/a"}</dd>
            <dt>Ask</dt><dd>{t ? t.ask.toFixed(d) : "n/a"}</dd>
            <dt>Spread (pts)</dt><dd>{t ? t.spread_points : "n/a"}</dd>
            <dt>Last close</dt><dd>{lastBar ? lastBar.close : "n/a"}</dd>
            <dt>Change (window)</dt><dd className={chg >= 0 ? "up" : "down"}>{lastBar ? `${chg.toFixed(d)} (${pct.toFixed(2)}%)` : "n/a"}</dd>
            <dt>High (last 288 bars)</dt><dd>{hi ?? "n/a"}</dd>
            <dt>Low (last 288 bars)</dt><dd>{lo ?? "n/a"}</dd>
            <dt>Market</dt><dd>{t ? (t.market_open ? "Open" : "Closed") : "Unknown"}</dd>
          </dl>
          {!t && <p className="note">No live quote. Bid, ask and spread need a connected MT5 terminal.</p>}
          <OrderPanel symbol={symbol} status={status} onDone={() => setRk(k => k + 1)} notify={(m, k) => { if (cached()?.notifications.order_results ?? true) notify?.(m, k); }} />
          <AutoTrader symbol={symbol} tf={tf} status={status} />
        </aside>
      </div>
      <div className="dock"><Positions refreshKey={rk} />{["M5", "M15", "H1"].includes(tf) && symbol ? <SignalCard symbol={symbol} tf={tf} /> : <section className="dockpane"><h4>Research signal</h4><p className="note">Models exist for M5, M15 and H1 only.</p></section>}</div>
    </div>
  );
}
