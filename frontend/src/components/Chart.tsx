import { useEffect, useRef } from "react";
import { createChart, UTCTimestamp } from "lightweight-charts";
type Line = { y: number[]; color: string; w?: number; op?: number; dash?: string; name?: string };
type Band = { lo: number[]; hi: number[]; color: string; op?: number };
const fmt = (v: number) => (Math.abs(v) >= 1000 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : Math.abs(v) >= 0.1 ? v.toFixed(3) : v.toPrecision(3));

export function Chart({ x, lines = [], bands = [], hline, h = 240, xLabel = "", yLabel = "" }: { x: number[]; lines?: Line[]; bands?: Band[]; hline?: number; h?: number; xLabel?: string; yLabel?: string }) {
  const W = 640, L = 54, R = 10, T = 8, B = 28;
  const all = [...lines.flatMap(l => l.y), ...bands.flatMap(b => [...b.lo, ...b.hi]), ...(hline != null ? [hline] : [])].filter(Number.isFinite);
  let y0 = Math.min(...all), y1 = Math.max(...all); if (y0 === y1) { y0 -= 1; y1 += 1; }
  const x0 = Math.min(...x), x1 = Math.max(...x), sx = (v: number) => L + ((v - x0) / (x1 - x0 || 1)) * (W - L - R), sy = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (h - T - B);
  const path = (ys: number[]) => ys.map((v, i) => `${i ? "L" : "M"}${sx(x[i]).toFixed(1)},${sy(v).toFixed(1)}`).join("");
  const ticks = [0, 1, 2, 3, 4];
  return (
    <svg viewBox={`0 0 ${W} ${h}`} className="svgchart" role="img" aria-label={`${yLabel} versus ${xLabel}`}>
      {ticks.map(i => { const v = y0 + ((y1 - y0) * i) / 4; return <g key={i}><line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} stroke="#1d222a" /><text x={L - 6} y={sy(v) + 3} fill="#8b94a3" fontSize="10" textAnchor="end">{fmt(v)}</text></g>; })}
      {ticks.map(i => { const v = x0 + ((x1 - x0) * i) / 4; return <text key={i} x={sx(v)} y={h - 14} fill="#8b94a3" fontSize="10" textAnchor="middle">{fmt(v)}</text>; })}
      <text x={(L + W) / 2} y={h - 2} fill="#8b94a3" fontSize="10" textAnchor="middle">{xLabel}</text>
      {bands.map((b, i) => <path key={i} d={path(b.hi) + [...b.lo].reverse().map((v, j) => `L${sx(x[b.lo.length - 1 - j]).toFixed(1)},${sy(v).toFixed(1)}`).join("") + "Z"} fill={b.color} opacity={b.op ?? 0.2} />)}
      {hline != null && <line x1={L} x2={W - R} y1={sy(hline)} y2={sy(hline)} stroke="#8b94a3" strokeDasharray="4 4" />}
      {lines.map((l, i) => <path key={i} d={path(l.y)} fill="none" stroke={l.color} strokeWidth={l.w ?? 1.5} opacity={l.op ?? 1} strokeDasharray={l.dash} />)}
    </svg>
  );
}

export function HistBars({ counts, edges, color = "#e0a526", split = 0 }: { counts: number[]; edges: number[]; color?: string; split?: number }) {
  const mx = Math.max(...counts, 1), n = counts.length, w = 600 / n;
  return <svg viewBox="0 0 600 120" className="svgchart" role="img" aria-label="distribution">
    {counts.map((c, i) => <rect key={i} x={i * w + 1} y={100 - (c / mx) * 95} width={w - 2} height={(c / mx) * 95} fill={(edges[i] + edges[i + 1]) / 2 >= split && color === "pn" ? "#3fb68b" : color === "pn" ? "#e5534b" : color} />)}
    <text x="0" y="115" fill="#8b94a3" fontSize="10">{fmt(edges[0])}</text><text x="600" y="115" fill="#8b94a3" fontSize="10" textAnchor="end">{fmt(edges[n])}</text></svg>;
}

export function TimeLine({ points, color = "#e0a526" }: { points: { time: number; value: number }[]; color?: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const c = createChart(el.current!, { autoSize: true, layout: { background: { color: "#14171c" }, textColor: "#8b94a3", fontFamily: "IBM Plex Mono" }, grid: { vertLines: { color: "#1d222a" }, horzLines: { color: "#1d222a" } }, rightPriceScale: { borderColor: "#2a303a" }, timeScale: { borderColor: "#2a303a", timeVisible: true } });
    const seen = new Set<number>(); c.addLineSeries({ color, lineWidth: 2 }).setData(points.filter(p => !seen.has(p.time) && seen.add(p.time)).map(p => ({ time: p.time as UTCTimestamp, value: p.value })));
    c.timeScale().fitContent(); return () => c.remove();
  }, [points, color]);
  return <div ref={el} className="eq" />;
}

export function PnlBars({ labels, values }: { labels: string[]; values: number[] }) {
  const W = 640, H = 200, L = 54, R = 10, T = 8, B = 22, mx = Math.max(...values.map(Math.abs), 1), bw = (W - L - R) / Math.max(values.length, 1), zy = T + (H - T - B) / 2, half = zy - T;
  return <svg viewBox={`0 0 ${W} ${H}`} className="svgchart" role="img" aria-label="daily profit and loss">
    <line x1={L} x2={W - R} y1={zy} y2={zy} stroke="#2a303a" /><text x={L - 6} y={T + 8} fill="#8b94a3" fontSize="10" textAnchor="end">{fmt(mx)}</text><text x={L - 6} y={H - B} fill="#8b94a3" fontSize="10" textAnchor="end">{fmt(-mx)}</text>
    {values.map((v, i) => <rect key={i} x={L + i * bw + 1} y={v >= 0 ? zy - (v / mx) * half : zy} width={Math.max(bw - 2, 1)} height={(Math.abs(v) / mx) * half} fill={v >= 0 ? "#3fb68b" : "#e5534b"} />)}
    {labels.length > 0 && <><text x={L} y={H - 6} fill="#8b94a3" fontSize="10">{labels[0]}</text><text x={W - R} y={H - 6} fill="#8b94a3" fontSize="10" textAnchor="end">{labels[labels.length - 1]}</text></>}</svg>;
}

export function HBars({ rows }: { rows: { label: string; pct: number; text: string; color?: string }[] }) {
  return <div className="hbars">{rows.map(r => <div key={r.label}><span>{r.label}</span><div className="track"><i style={{ width: `${Math.max(0, Math.min(100, r.pct))}%`, background: r.color ?? "#e0a526" }} /></div><b>{r.text}</b></div>)}</div>;
}
