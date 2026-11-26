import { useState } from "react";
import { api, Status, Validation, Execution, OrderIn } from "../services/api";

const num = (s: string) => (s.trim() === "" ? null : Number(s));
export default function OrderPanel({ symbol, status, onDone, notify }: { symbol: string; status: Status | null; onDone: () => void; notify?: (m: string, k?: "ok" | "err") => void }) {
  const [side, setSide] = useState<"buy" | "sell">("buy"); const [otype, setOtype] = useState("market");
  const [vol, setVol] = useState("0.01"), [sl, setSl] = useState(""), [tp, setTp] = useState(""), [price, setPrice] = useState("");
  const [val, setVal] = useState<Validation | null>(null), [res, setRes] = useState<Execution | null>(null);
  const [busy, setBusy] = useState(false), [confirm, setConfirm] = useState(false), [msg, setMsg] = useState("");
  const allowed = !!status?.connected && status.trading_allowed;
  const order = (): OrderIn => ({ symbol, side, volume: Number(vol), order_type: otype, price: num(price), sl: num(sl), tp: num(tp) });
  const run = async (f: () => Promise<void>) => { setBusy(true); setMsg(""); try { await f(); } catch (e) { setMsg((e as Error).message); } setBusy(false); };

  return (
    <section className="order">
      <h4>Order <span className="sub">{allowed ? status!.trading_reason : status?.connected ? status.trading_reason : "MT5 disconnected: trading disabled"}</span></h4>
      <div className="seg">
        <button className={side === "buy" ? "buy on" : "buy"} onClick={() => { setSide("buy"); setConfirm(false); }}>Buy</button>
        <button className={side === "sell" ? "sell on" : "sell"} onClick={() => { setSide("sell"); setConfirm(false); }}>Sell</button>
      </div>
      <label>Type<select value={otype} onChange={e => setOtype(e.target.value)}><option value="market">Market</option><option value="limit">Limit</option><option value="stop">Stop</option></select></label>
      {otype !== "market" && <label>Price<input value={price} onChange={e => setPrice(e.target.value)} inputMode="decimal" /></label>}
      <label>Lots<input value={vol} onChange={e => { setVol(e.target.value); setConfirm(false); }} inputMode="decimal" /></label>
      <label>Stop-loss<input value={sl} onChange={e => setSl(e.target.value)} inputMode="decimal" placeholder="required" /></label>
      <label>Take-profit<input value={tp} onChange={e => setTp(e.target.value)} inputMode="decimal" placeholder="optional" /></label>
      <div className="row">
        <button disabled={!allowed || busy || !num(sl)} onClick={() => run(async () => { const r = await api.size(symbol, side, Number(sl)); setVol(String(r.volume)); })}>Size by risk</button>
        <button disabled={!allowed || busy} onClick={() => run(async () => { setRes(null); setVal(await api.validate(order())); })}>Validate</button>
      </div>
      {!confirm
        ? <button className={`go ${side}`} disabled={!allowed || busy} onClick={() => setConfirm(true)}>Place {side.toUpperCase()} {vol} {symbol}</button>
        : <div className="row"><button className={`go ${side}`} disabled={busy} onClick={() => run(async () => { const r = await api.submit(order()); setRes(r); setVal(r); setConfirm(false); onDone(); notify?.(r.executed ? `Order executed: ${order().side} ${order().volume} ${symbol}` : `Order rejected (${r.stage}): ${r.reason}`, r.executed ? "ok" : "err"); })}>Confirm</button>
            <button onClick={() => setConfirm(false)}>Cancel</button></div>}
      {msg && <p className="err">{msg}</p>}
      {val && <ul className="checks">
        {val.risk?.checks.map(c => <li key={c.name} className={c.passed ? "ok" : "bad"}>{c.passed ? "✓" : "✗"} {c.detail}</li>)}
        {!val.risk && val.reason && <li className="bad">✗ {val.stage}: {val.reason}</li>}
        {val.risk && !val.approved && val.stage === "broker_check" && <li className="bad">✗ broker check: {val.reason}</li>}
      </ul>}
      {res && (res.executed
        ? <p className="ok">Executed ({res.state}) @ {res.result?.price} · MT5 time {res.latency_exec_ms?.toFixed(0)} ms</p>
        : <p className="err">Rejected at {res.stage}: {res.reason}</p>)}
    </section>
  );
}
