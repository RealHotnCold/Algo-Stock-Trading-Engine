import { useEffect, useState } from "react";
import { api, Status } from "../services/api";

const time = (t: number) => new Date(t * 1000).toTimeString().slice(0, 8);
const utc = (t: number) => new Date(t * 1000).toISOString().slice(11, 16);
export default function AutoTrader({ symbol, tf, status }: { symbol: string; tf: string; status: Status | null }) {
  const [s, setS] = useState<any>(null), [err, setErr] = useState(""), [confirm, setConfirm] = useState(false), [max, setMax] = useState(5), [busy, setBusy] = useState(false), [pv, setPv] = useState<any>(null);
  const preview = () => { setBusy(true); setErr(""); api.autoPreview({ symbol, tf }).then(setPv).catch(e => { setPv(null); setErr(e.message); }).finally(() => setBusy(false)); };
  const load = () => api.autoStatus().then(x => { setS(x); setErr(""); }).catch(e => setErr(e.message));
  useEffect(() => { load(); const i = setInterval(load, 3000); return () => clearInterval(i); }, []);
  const eligible = symbol.toUpperCase().startsWith("EURUSD") && ["M5", "M15", "H1"].includes(tf);
  const demo = !!status?.connected && status.trading_allowed && status.account?.kind === "demo";
  const act = (f: () => Promise<any>) => { setBusy(true); setErr(""); f().then(x => { setS(x); setConfirm(false); }).catch(e => setErr(e.message)).finally(() => setBusy(false)); };
  const d = s?.last_decision;
  return (
    <section className="auto">
      <h4>Auto-trader <span className="sub">demo accounts only</span></h4>
      {s?.running ? <>
        <p className="ok">Running on {s.symbol} {s.tf}: one decision per closed candle · {s.trades_today}/{s.max_trades_per_day} new trades today{s.consecutive_failures ? ` · ${s.consecutive_failures} recent failures` : ""}</p>
        <p className="note">Alive: last check {s.last_check ? time(s.last_check) : "–"} · next candle closes about {s.next_candle_close ? utc(s.next_candle_close) : "–"} (broker time). It only acts when a candle closes.</p>
        {d && <p className="note">Last candle: {d.decision}, {(d.confidence * 100).toFixed(0)}% confidence, regime {d.regime}</p>}
        <div className="row"><button className="go sell" disabled={busy} onClick={() => act(() => api.autoStop(false))}>Stop</button><button disabled={busy} onClick={() => act(() => api.autoStop(true))}>Stop and close its positions</button></div>
      </> : <>
        {s?.log?.length > 0 && !s.running && <p className="note">Stopped.</p>}
        {!confirm ? <button className="go buy" disabled={!eligible || !demo || busy} onClick={() => setConfirm(true)}>Start auto-trader…</button> : <div className="confirmbox">
          <p>This places <b>orders on your demo account</b> by itself, one decision per closed {tf} candle on {symbol}, through the same risk checks as manual orders. In testing the strategy <b>lost money</b>, so expect losses. Stop it any time.</p>
          <label>Max new trades per day<input type="number" min={1} max={50} value={max} onChange={e => setMax(Number(e.target.value))} /></label>
          <div className="row"><button className="go buy" disabled={busy} onClick={() => act(() => api.autoStart({ symbol, tf, max_trades_per_day: max }))}>I understand, start</button><button onClick={() => setConfirm(false)}>Cancel</button></div></div>}
        {!demo && <p className="note">{status?.connected ? "Needs a demo account with trading allowed." : "Needs MT5 connected to a demo account."}</p>}
        {demo && !eligible && <p className="note">The model is trained on EURUSD, M5, M15 and H1 only.</p>}
      </>}
      <button disabled={!eligible || !status?.connected || busy} onClick={preview}>Check now (places no order)</button>
      {pv && <div className="note"><p>Latest closed candle {utc(pv.bar_time)}: <b>{pv.decision}</b>, {(pv.confidence * 100).toFixed(0)}% confidence, regime {pv.regime}. Model wants {pv.target > 0 ? "long" : pv.target < 0 ? "short" : "flat"}; holding {pv.current > 0 ? "long" : pv.current < 0 ? "short" : "nothing"}.</p>
        {pv.order && <p>Would place: {pv.order.side.toUpperCase()} {pv.order.volume} lots, SL {pv.order.sl}, TP {pv.order.tp}. {pv.note}</p>}{!pv.order && <p>{pv.note}</p>}
        {pv.validation && <ul className="checks">{pv.validation.risk?.checks.map((c: any) => <li key={c.name} className={c.passed ? "ok" : "bad"}>{c.passed ? "✓" : "✗"} {c.detail}</li>)}{!pv.validation.risk && <li className="bad">✗ {pv.validation.stage}: {pv.validation.reason}</li>}{pv.validation.risk && !pv.validation.approved && pv.validation.stage === "broker_check" && <li className="bad">✗ broker check: {pv.validation.reason}</li>}{pv.validation.approved && <li className="ok">All checks pass: it would be sent.</li>}</ul>}</div>}
      {err && <p className="err">{err}</p>}
      {s?.log?.length > 0 && <ul className="autolog">{[...s.log].reverse().slice(0, 12).map((l: any, i: number) => <li key={i}><span>{time(l.t)}</span> {l.msg}</li>)}</ul>}
    </section>
  );
}
