import { useEffect, useState } from "react";
import { api, Position } from "../services/api";

export default function Positions({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<Position[]>([]); const [err, setErr] = useState("");
  const load = () => api.positions().then(r => { setRows(r); setErr(""); }).catch(e => { setRows([]); setErr(e.message); });
  useEffect(() => { load(); const i = setInterval(load, 2000); return () => clearInterval(i); }, [refreshKey]);
  const total = rows.reduce((a, p) => a + p.profit, 0);
  return (
    <section className="dockpane"><h4>Open positions {rows.length > 0 && <span className={`sub ${total >= 0 ? "up" : "down"}`}>{total.toFixed(2)}</span>}</h4>
      {err ? <p className="note">{err}</p> : rows.length === 0 ? <p className="note">No open positions.</p> :
        <table><thead><tr><th>Symbol</th><th>Side</th><th>Lots</th><th>Open</th><th>SL</th><th>TP</th><th>P&L</th><th /></tr></thead><tbody>
          {rows.map(p => <tr key={p.ticket}><td>{p.symbol}</td><td className={p.side === "buy" ? "up" : "down"}>{p.side}</td><td>{p.volume}</td><td>{p.price_open}</td><td>{p.sl || "–"}</td><td>{p.tp || "–"}</td>
            <td className={p.profit >= 0 ? "up" : "down"}>{p.profit.toFixed(2)}</td>
            <td><button onClick={() => api.close(p.ticket).then(r => { if (!r.closed) alert(r.result.comment); load(); })}>Close</button></td></tr>)}
        </tbody></table>}
    </section>
  );
}
