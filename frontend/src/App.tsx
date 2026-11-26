import { useEffect, useRef, useState } from "react";
import { cached, loadSettings } from "./services/settings";
import Settings from "./pages/Settings";
import { api, Status } from "./services/api";
import Terminal from "./pages/Terminal";
import Research from "./pages/Research";
import Backtest from "./pages/Backtest";
import SimLab from "./pages/SimLab";
import Portfolio from "./pages/Portfolio";
import TradeHistory from "./pages/TradeHistory";

const TABS = ["Market terminal", "Research strategy", "Simulation lab", "Backtesting", "Portfolio & risk", "Trade history", "Settings"];

function Badge({ s }: { s: Status | null }) {
  if (!s) return <span className="badge off">Connecting…</span>;
  if (!s.connected) return <span className="badge off" title={s.reason}>MT5 disconnected</span>;
  const k = s.account!.kind;
  return <span className={`badge ${k === "demo" ? "demo" : "real"}`}>{k === "demo" ? "Demo account" : k === "real" ? "REAL account" : k} · {s.account!.login} · {s.account!.currency} {s.account!.equity.toFixed(2)}</span>;
}

export default function App() {
  const [tab, setTab] = useState(TABS[0]); const [status, setStatus] = useState<Status | null>(null);
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([]); const prev = useRef<boolean | null>(null);
  const notify = (msg: string, kind: "ok" | "err" = "ok") => { const id = Math.random(); setToasts(t => [...t, { id, msg, kind }]); setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000); };
  useEffect(() => { loadSettings().catch(() => {}); }, []);
  useEffect(() => { if (!status) return; if (prev.current !== null && prev.current !== status.connected && (cached()?.notifications.connection_changes ?? true)) notify(status.connected ? "MT5 connected" : `MT5 disconnected${status.reason ? `: ${status.reason}` : ""}`, status.connected ? "ok" : "err"); prev.current = status.connected; }, [status]);
  useEffect(() => { const f = () => api.status().then(setStatus).catch(() => setStatus({ connected: false, reason: "backend unreachable", demo_only: true, trading_allowed: false, trading_reason: "disconnected" })); f(); const i = setInterval(f, 5000); return () => clearInterval(i); }, []);
  return (
    <div className="app">
      <header>
        <nav>{TABS.map(t => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}</nav>
        <div className="right">{status?.demo_only && <span className="mode">Demo-only mode</span>}<Badge s={status} /></div>
      </header>
      {tab === TABS[0] ? <Terminal status={status} notify={notify} /> : tab === "Research strategy" ? <Research /> : tab === "Backtesting" ? <Backtest /> : tab === "Simulation lab" ? <SimLab /> : tab === "Portfolio & risk" ? <Portfolio /> : tab === "Trade history" ? <TradeHistory /> : <Settings status={status} onStatus={setStatus} />}
      <div className="toasts" aria-live="polite">{toasts.map(t => <div key={t.id} className={`toast ${t.kind}`}>{t.msg}</div>)}</div>
    </div>
  );
}
