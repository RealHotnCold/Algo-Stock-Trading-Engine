import { useEffect, useState } from "react";
import { api, Status, RiskCfg } from "../services/api";
import { loadSettings, saveSettings } from "../services/settings";

const Num = ({ l, v, set, step }: { l: string; v: number; set: (n: number) => void; step?: string }) => <label>{l}<input type="number" step={step ?? "any"} value={Number.isFinite(v) ? v : ""} onChange={e => set(e.target.value === "" ? NaN : Number(e.target.value))} /></label>;
const Chk = ({ l, v, set }: { l: string; v: boolean; set: (b: boolean) => void }) => <label className="chk"><input type="checkbox" checked={v} onChange={e => set(e.target.checked)} />{l}</label>;
const TFS = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"];

export default function Settings({ status, onStatus }: { status: Status | null; onStatus: (s: Status) => void }) {
  const [s, setS] = useState<any>(null), [risk, setRisk] = useState<any>(null), [symbols, setSymbols] = useState<string[]>([]), [q, setQ] = useState("");
  const [msg, setMsg] = useState<{ t: string; ok: boolean } | null>(null), [rmsg, setRmsg] = useState<{ t: string; ok: boolean } | null>(null), [busy, setBusy] = useState(false);
  useEffect(() => { loadSettings().then(setS).catch(e => setMsg({ t: e.message, ok: false })); api.risk().then(setRisk).catch(() => {}); api.symbols().then(r => setSymbols(r.symbols.map(x => x.name))).catch(() => {}); }, []);
  if (!s) return <div className="page doc"><p className="note">{msg ? msg.t : "Loading…"}</p></div>;
  const up = (sec: string, k: string, v: unknown) => setS((o: any) => ({ ...o, [sec]: { ...o[sec], [k]: v } }));
  const save = () => saveSettings({ general: s.general, chart: { show_volume: s.chart.show_volume, show_grid: s.chart.show_grid }, notifications: s.notifications, strategy: s.strategy, simulation: s.simulation })
    .then(x => { setS(x); setMsg({ t: "Saved. Open pages pick up chart and default changes the next time they load.", ok: true }); }).catch(e => setMsg({ t: e.message, ok: false }));
  const saveRisk = () => api.setRisk(risk).then(x => { setRisk(x); setRmsg({ t: "Risk limits applied and saved. The risk engine uses them for the next order.", ok: true }); }).catch(e => setRmsg({ t: e.message, ok: false }));
  const reconnect = () => { setBusy(true); api.reconnect().then(onStatus).finally(() => setBusy(false)); };
  const a = status?.account, fav: string[] = s.general.favourites, match = symbols.filter(n => n.toLowerCase().includes(q.toLowerCase())).slice(0, 40);
  const toggleFav = (n: string) => up("general", "favourites", fav.includes(n) ? fav.filter(x => x !== n) : [...fav, n]);
  const session = risk?.session_utc_hours as number[] | null;
  return (
    <div className="page doc wide settings">
      <h2>Settings</h2>
      <section className="sec"><h3>MT5 connection &amp; account</h3>
        <dl className="kv"><dt>Connection</dt><dd className={status?.connected ? "up" : "down"}>{status?.connected ? "Connected" : `Disconnected${status?.reason ? ` (${status.reason})` : ""}`}</dd>
          {a && <><dt>Account type</dt><dd>{a.kind === "demo" ? "Demo" : a.kind.toUpperCase()}</dd><dt>Broker / server</dt><dd>{a.broker} · {a.server}</dd><dt>Login</dt><dd>{a.login}</dd><dt>Currency / leverage</dt><dd>{a.currency} · 1:{a.leverage}</dd></>}
          <dt>Demo-only mode</dt><dd>{status?.demo_only ? "ON" : "OFF"}</dd><dt>Trading allowed</dt><dd>{status?.trading_allowed ? "Yes" : "No"} <span className="note">({status?.trading_reason})</span></dd></dl>
        <button onClick={reconnect} disabled={busy}>{busy ? "Connecting…" : "Reconnect to MT5"}</button>
        <p className="note">Demo-only mode and real-account permission are set in <code>backend/.env</code> (<code>DEMO_ONLY</code>, <code>ALLOW_REAL_TRADING</code>) and need a backend restart. They are deliberately not switchable from this page, so real-money trading cannot be enabled by accident. MT5 credentials are never shown here or stored in the browser; by default the app uses the terminal's logged-in session.</p></section>
      <section className="sec"><h3>Instruments &amp; defaults</h3>
        <div className="form"><label>Default symbol<select value={s.general.default_symbol} onChange={e => up("general", "default_symbol", e.target.value)}><option value="">First available</option>{symbols.map(n => <option key={n}>{n}</option>)}</select></label>
          <label>Default timeframe<select value={s.general.default_timeframe} onChange={e => up("general", "default_timeframe", e.target.value)}>{TFS.map(t => <option key={t}>{t}</option>)}</select></label></div>
        <h4>Favourite instruments (listed first in the terminal)</h4>
        <div className="chips">{fav.map(n => <button key={n} onClick={() => toggleFav(n)} aria-label={`remove ${n}`}>{n} ✕</button>)}{!fav.length && <span className="note">None selected.</span>}</div>
        <input placeholder={symbols.length ? "Filter instruments…" : "No instruments yet (connect MT5 or import data)"} value={q} onChange={e => setQ(e.target.value)} disabled={!symbols.length} style={{ maxWidth: 280, margin: "8px 0" }} />
        <div className="symlist">{match.map(n => <label key={n} className="chk"><input type="checkbox" checked={fav.includes(n)} onChange={() => toggleFav(n)} />{n}</label>)}</div>
        <p className="note">The instrument list comes from the connected MT5 terminal, or from imported history when disconnected.</p></section>
      <section className="sec"><h3>Chart preferences</h3>
        <div className="form"><Chk l="Show volume" v={s.chart.show_volume} set={v => up("chart", "show_volume", v)} /><Chk l="Show grid" v={s.chart.show_grid} set={v => up("chart", "show_grid", v)} /></div>
        <p className="note">Indicators are added from the Indicators button above the chart and are remembered automatically.</p></section>
      <section className="sec"><h3>Strategy parameters (defaults for Backtesting)</h3>
        <div className="form"><Num l="Risk per trade (%)" v={s.strategy.risk_pct} set={v => up("strategy", "risk_pct", v)} /><Num l="Stop-loss (× ATR)" v={s.strategy.sl_atr} set={v => up("strategy", "sl_atr", v)} /><Num l="Take-profit (× ATR)" v={s.strategy.tp_atr} set={v => up("strategy", "tp_atr", v)} />
          <Num l="Slippage (pips)" v={s.strategy.slippage_pips} set={v => up("strategy", "slippage_pips", v)} /><Num l="Stop-out cooldown (bars)" v={s.strategy.cooldown_bars} step="1" set={v => up("strategy", "cooldown_bars", v)} /></div></section>
      <section className="sec"><h3>Simulation parameters (defaults for Monte Carlo)</h3>
        <div className="form"><Num l="Capital" v={s.simulation.capital} set={v => up("simulation", "capital", v)} /><Num l="Simulations" v={s.simulation.n_sims} step="1" set={v => up("simulation", "n_sims", v)} /><Num l="Horizon (bars)" v={s.simulation.horizon} step="1" set={v => up("simulation", "horizon", v)} />
          <Num l="Leverage (×)" v={s.simulation.leverage} set={v => up("simulation", "leverage", v)} /><Num l="Bootstrap block (bars)" v={s.simulation.block} step="1" set={v => up("simulation", "block", v)} /></div></section>
      <section className="sec"><h3>Notifications</h3>
        <div className="form"><Chk l="Alert when MT5 connects or disconnects" v={s.notifications.connection_changes} set={v => up("notifications", "connection_changes", v)} /><Chk l="Alert with the result of each order" v={s.notifications.order_results} set={v => up("notifications", "order_results", v)} /></div></section>
      <div className="row" style={{ alignItems: "center" }}><button className="go buy" style={{ width: "auto" }} onClick={save}>Save settings</button>{msg && <span className={msg.ok ? "ok" : "err"}>{msg.t}</span>}</div>
      {risk && <section className="sec"><h3>Risk parameters (enforced by the risk engine)</h3>
        <div className="form"><Num l="Max risk per trade (% equity)" v={risk.risk_per_trade_pct} set={v => setRisk({ ...risk, risk_per_trade_pct: v })} /><Num l="Max daily loss (% balance)" v={risk.max_daily_loss_pct} set={v => setRisk({ ...risk, max_daily_loss_pct: v })} />
          <Num l="Max open positions" v={risk.max_open_positions} step="1" set={v => setRisk({ ...risk, max_open_positions: v })} /><Num l="Max lots per symbol" v={risk.max_lots_per_symbol} set={v => setRisk({ ...risk, max_lots_per_symbol: v })} />
          <Num l="Max total lots" v={risk.max_total_lots} set={v => setRisk({ ...risk, max_total_lots: v })} /><Num l="Min reward : risk (when TP set)" v={risk.min_reward_risk} set={v => setRisk({ ...risk, min_reward_risk: v })} />
          <Num l="Max spread (points)" v={risk.max_spread_points} set={v => setRisk({ ...risk, max_spread_points: v })} /><Chk l="Require a stop-loss" v={risk.require_stop_loss} set={v => setRisk({ ...risk, require_stop_loss: v })} />
          <Chk l="Volatility filter (ATR(14) on M5)" v={!!risk.vol_filter} set={v => setRisk({ ...risk, vol_filter: v })} />
          {risk.vol_filter && <><Num l="Min ATR (points)" v={risk.min_atr_points} set={v => setRisk({ ...risk, min_atr_points: v })} /><Num l="Max ATR (points, 0 = no cap)" v={risk.max_atr_points} set={v => setRisk({ ...risk, max_atr_points: v })} /></>}
          <Chk l="Restrict to a trading session (UTC)" v={!!session} set={v => setRisk({ ...risk, session_utc_hours: v ? [7, 17] : null })} />
          {session && <><Num l="Session start hour" v={session[0]} step="1" set={v => setRisk({ ...risk, session_utc_hours: [v, session[1]] })} /><Num l="Session end hour" v={session[1]} step="1" set={v => setRisk({ ...risk, session_utc_hours: [session[0], v] })} /></>}</div>
        <div className="row" style={{ alignItems: "center" }}><button onClick={saveRisk}>Apply risk limits</button>{rmsg && <span className={rmsg.ok ? "ok" : "err"}>{rmsg.t}</span>}</div>
        <p className="note">Limits survive a backend restart. The volatility filter rejects orders when recent M5 volatility is outside your range, and also rejects them if ATR cannot be fetched.</p></section>}
    </div>
  );
}
