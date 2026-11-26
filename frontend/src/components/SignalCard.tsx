import { useEffect, useState } from "react";
import { api, Signal } from "../services/api";

export default function SignalCard({ symbol, tf = "M5", full = false }: { symbol: string; tf?: string; full?: boolean }) {
  const [s, setS] = useState<Signal | null>(null); const [err, setErr] = useState("");
  useEffect(() => { if (!symbol) return; const f = () => api.signal(symbol, tf).then(x => { setS(x); setErr(""); }).catch(e => { setS(null); setErr(e.message); }); f(); const i = setInterval(f, 15000); return () => clearInterval(i); }, [symbol, tf]);
  return (
    <section className="dockpane"><h4>Research signal <span className="sub">experimental · advisory only · {tf} model</span></h4>
      {err && <p className="note">{err}</p>}
      {s && <>
        <p className="sig"><b className={s.decision === "Buy" ? "up" : s.decision === "Sell" ? "down" : ""}>{s.decision}</b> · regime {s.regime} · confidence {(s.confidence * 100).toFixed(0)}% (needs ≥{(s.threshold * 100).toFixed(0)}%){s.abstain_reason && ` · ${s.abstain_reason}`}
          <span className="sub"> · {s.data_source} · inference {s.latency_infer_ms.toFixed(0)} ms · {s.memory_neighbors} memory neighbours</span></p>
        <table><thead><tr><th>Agent</th><th>Action</th><th>Conf.</th><th>Weight</th><th>Memory (bps)</th>{full && <th>Why</th>}</tr></thead><tbody>
          {s.agents.map(a => <tr key={a.agent}><td>{a.agent}</td><td>{a.action}</td><td>{(a.confidence * 100).toFixed(0)}%</td><td>{a.base_weight.toFixed(2)}</td><td>{a.memory_outcome_bps.toFixed(2)}</td>{full && <td className="why">{a.rationale}</td>}</tr>)}
        </tbody></table>
        <p className="note">The risk engine still vets any trade. No automatic execution is wired up.</p></>}
    </section>
  );
}
