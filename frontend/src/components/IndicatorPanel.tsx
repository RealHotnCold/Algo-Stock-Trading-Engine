import { useState } from "react";
import { INFO, PALETTE, Ind, IndType } from "../utils/indicators";

export default function IndicatorPanel({ inds, onChange }: { inds: Ind[]; onChange: (i: Ind[]) => void }) {
  const [type, setType] = useState<IndType>("SMA");
  const add = () => onChange([...inds, { id: Math.random().toString(36).slice(2, 8), type, params: { ...INFO[type].params } }]);
  const setParam = (id: string, k: string, v: number) => onChange(inds.map(i => (i.id === id ? { ...i, params: { ...i.params, [k]: v } } : i)));
  return (
    <div className="indpanel" role="dialog" aria-label="Indicators">
      <div className="row"><select value={type} onChange={e => setType(e.target.value as IndType)} aria-label="indicator type">{(Object.keys(INFO) as IndType[]).map(t => <option key={t} value={t}>{INFO[t].label}</option>)}</select><button onClick={add} disabled={inds.length >= 12}>Add</button></div>
      {inds.length === 0 && <p className="note">No indicators. Add several (for example two SMAs) to compare them. They are calculated from the bars on the chart.</p>}
      {inds.map((i, idx) => <div key={i.id} className="indrow"><span style={{ color: PALETTE[idx % PALETTE.length] }}>■</span><b>{i.type}</b>
        {Object.entries(i.params).map(([k, v]) => <label key={k}>{k}<input type="number" min={1} step={k === "mult" ? 0.5 : 1} value={Number.isFinite(v) ? v : ""} onChange={e => setParam(i.id, k, e.target.value === "" ? NaN : Number(e.target.value))} /></label>)}
        <button onClick={() => onChange(inds.filter(x => x.id !== i.id))} aria-label={`remove ${i.type}`}>✕</button></div>)}
    </div>
  );
}
