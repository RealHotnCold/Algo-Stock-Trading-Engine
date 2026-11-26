import { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, IPriceLine, CrosshairMode, UTCTimestamp } from "lightweight-charts";
import type { Bar, Drawing } from "../services/api";
import { compute, INFO, PALETTE, Ind } from "../utils/indicators";

const UP = "#3fb68b", DOWN = "#e5534b", BAND = 0.16;
export type Marker = { time: number; position: "aboveBar" | "belowBar"; color: string; shape: "arrowUp" | "arrowDown" | "circle"; text?: string };
type Built = { ind: Ind; series: ISeriesApi<any>[] };
export default function PriceChart({ bars, live, markers, indicators = [], showVolume = true, showGrid = true, drawings = [], onChartClick, tool = "none" }: { bars: Bar[]; live?: { price: number; time: number } | null; markers?: Marker[]; indicators?: Ind[]; showVolume?: boolean; showGrid?: boolean; drawings?: Drawing[]; onChartClick?: (p: { time: number; price: number }) => void; tool?: string }) {
  const clickRef = useRef(onChartClick); clickRef.current = onChartClick; const drawn = useRef<{ lines: IPriceLine[]; series: ISeriesApi<any>[] }>({ lines: [], series: [] });
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi>(); const candles = useRef<ISeriesApi<"Candlestick">>(); const vol = useRef<ISeriesApi<"Histogram">>();
  const last = useRef<Bar>(); const cur = useRef<Bar[]>([]); const built = useRef<Built[]>([]);

  const applyInd = () => {
    const bs = cur.current; if (!bs.length) return; const t = bs.map(b => b.time as UTCTimestamp);
    built.current.forEach(({ ind, series }) => {
      const r = compute(ind, bs);
      series.forEach((s, k) => s.setData(r[k].flatMap((v, i) => (v == null ? [] : [ind.type === "MACD" && k === 0 ? { time: t[i], value: v, color: v >= 0 ? "#3fb68b88" : "#e5534b88" } : { time: t[i], value: v }])) as any));
    });
  };

  useEffect(() => {
    const c = createChart(el.current!, { autoSize: true, crosshair: { mode: CrosshairMode.Normal },
      layout: { background: { color: "#14171c" }, textColor: "#8b94a3", fontFamily: "IBM Plex Mono" },
      grid: { vertLines: { color: "#1d222a" }, horzLines: { color: "#1d222a" } },
      rightPriceScale: { borderColor: "#2a303a" }, timeScale: { borderColor: "#2a303a", timeVisible: true } });
    candles.current = c.addCandlestickSeries({ upColor: UP, downColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, borderVisible: false });
    vol.current = c.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", priceLineVisible: false, lastValueVisible: false });
    c.subscribeClick(p => { if (!p.point || p.time == null || !clickRef.current) return; const price = candles.current?.coordinateToPrice(p.point.y); if (price != null) clickRef.current({ time: p.time as number, price }); });
    chart.current = c; return () => { built.current = []; drawn.current = { lines: [], series: [] }; c.remove(); };
  }, []);

  useEffect(() => {
    candles.current?.setData(bars.map(b => ({ ...b, time: b.time as UTCTimestamp })));
    vol.current?.setData(bars.map(b => ({ time: b.time as UTCTimestamp, value: b.volume, color: b.close >= b.open ? "#3fb68b55" : "#e5534b55" })));
    last.current = bars[bars.length - 1]; cur.current = bars; applyInd(); chart.current?.timeScale().fitContent();
  }, [bars]);

  useEffect(() => {   // indicator panes: price overlays share the main scale, RSI/MACD/ATR/OBV each get their own band under it
    const c = chart.current; if (!c) return;
    built.current.forEach(b => b.series.forEach(s => c.removeSeries(s))); built.current = [];
    c.applyOptions({ grid: { vertLines: { visible: showGrid, color: "#1d222a" }, horzLines: { visible: showGrid, color: "#1d222a" } } });
    const subs = indicators.filter(i => INFO[i.type].pane === "sub"), mainBottom = subs.length * BAND;
    c.priceScale("right").applyOptions({ scaleMargins: { top: 0.05, bottom: mainBottom + (showVolume ? 0.17 : 0.03) } });
    vol.current?.applyOptions({ visible: showVolume });
    c.priceScale("vol").applyOptions({ scaleMargins: { top: 1 - mainBottom - 0.14, bottom: mainBottom } });
    indicators.forEach((ind, idx) => {
      const color = PALETTE[idx % PALETTE.length], pane = INFO[ind.type].pane, j = subs.indexOf(ind), sid = pane === "sub" ? `p-${ind.id}` : pane === "vol" ? "vol" : "right";
      const line = (o: object = {}) => c.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: pane === "sub", crosshairMarkerVisible: false, priceScaleId: sid, ...o } as any);
      let series: ISeriesApi<any>[];
      if (ind.type === "BB") series = [line({ color: color + "bb" }), line({ lineStyle: 2 }), line({ color: color + "bb" })];
      else if (ind.type === "MACD") series = [c.addHistogramSeries({ priceScaleId: sid, priceLineVisible: false, lastValueVisible: false } as any), line(), line({ color: "#8b94a3" })];
      else series = [line(ind.type === "SMA" || ind.type === "EMA" ? { lineWidth: 2 } : {})];
      if (ind.type === "RSI") [70, 30].forEach(p => series[0].createPriceLine({ price: p, color: "#8b94a3", lineWidth: 1, lineStyle: 3, axisLabelVisible: false, title: "" }));
      if (pane === "sub") { const top = 1 - mainBottom + j * BAND; c.priceScale(sid).applyOptions({ scaleMargins: { top: top + 0.015, bottom: Math.max(0, 1 - top - BAND) + 0.015 }, visible: true, borderColor: "#2a303a" }); }
      built.current.push({ ind, series });
    });
    applyInd();
  }, [indicators, showVolume, showGrid]);

  useEffect(() => {
    const t = bars.length ? bars[bars.length - 1].time : 0;
    candles.current?.setMarkers((markers ?? []).filter(m => m.time <= t).sort((a, b) => a.time - b.time).map(m => ({ ...m, time: m.time as UTCTimestamp })));
  }, [bars, markers]);

  useEffect(() => {   // user drawings: horizontal / support / resistance / alert lines are price lines, trend lines are two-point line series
    const c = chart.current, cs = candles.current; if (!c || !cs) return;
    drawn.current.lines.forEach(l => cs.removePriceLine(l)); drawn.current.series.forEach(s => c.removeSeries(s)); drawn.current = { lines: [], series: [] };
    drawings.forEach(d => {
      if (d.type === "trend") {
        const s = c.addLineSeries({ color: "#6aa8ff", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false } as any);
        s.setData([{ time: d.t1 as UTCTimestamp, value: d.p1 as number }, { time: d.t2 as UTCTimestamp, value: d.p2 as number }].sort((a, b) => (a.time as number) - (b.time as number))); drawn.current.series.push(s);
      } else {
        const st: Record<string, [string, number, string]> = { hline: ["#8b94a3", 2, ""], support: ["#3fb68b", 0, "S"], resistance: ["#e5534b", 0, "R"], alert: d.triggered ? ["#555e6b", 3, "alert (hit)"] : ["#e0a526", 1, `alert ${d.dir === "above" ? "▲" : "▼"}`] };
        const [color, lineStyle, title] = st[d.type]; drawn.current.lines.push(cs.createPriceLine({ price: d.price as number, color, lineWidth: 1, lineStyle, axisLabelVisible: true, title } as any));
      }
    });
  }, [drawings]);

  useEffect(() => {  // live tick only moves the forming bar; it never invents a new one
    const b = last.current; if (!live || !b || live.time < b.time) return;
    const u = { ...b, close: live.price, high: Math.max(b.high, live.price), low: Math.min(b.low, live.price) };
    last.current = u; cur.current = [...cur.current.slice(0, -1), u]; candles.current?.update({ ...u, time: u.time as UTCTimestamp }); applyInd();
  }, [live]);

  return <div ref={el} className={`chart${tool !== "none" ? " drawing" : ""}`} />;
}
