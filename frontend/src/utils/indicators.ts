// Indicators computed from the actual bars shown on the chart. Pure functions, no dependencies.
import type { Bar } from "../services/api";
export type IndType = "SMA" | "EMA" | "BB" | "VWAP" | "VOLMA" | "RSI" | "MACD" | "ATR" | "OBV";
export type Ind = { id: string; type: IndType; params: Record<string, number> };
type N = number | null;
export const INFO: Record<IndType, { label: string; params: Record<string, number>; pane: "price" | "vol" | "sub" }> = {
  SMA: { label: "SMA", params: { period: 20 }, pane: "price" }, EMA: { label: "EMA", params: { period: 20 }, pane: "price" },
  BB: { label: "Bollinger Bands", params: { period: 20, mult: 2 }, pane: "price" }, VWAP: { label: "VWAP (tick volume, resets daily UTC)", params: {}, pane: "price" },
  VOLMA: { label: "Volume MA", params: { period: 20 }, pane: "vol" }, RSI: { label: "RSI (Wilder)", params: { period: 14 }, pane: "sub" },
  MACD: { label: "MACD", params: { fast: 12, slow: 26, signal: 9 }, pane: "sub" }, ATR: { label: "ATR (Wilder)", params: { period: 14 }, pane: "sub" }, OBV: { label: "On-balance volume", params: {}, pane: "sub" } };
export const PALETTE = ["#e0a526", "#6aa8ff", "#c792ea", "#3fb68b", "#ff8a65", "#4dd0e1", "#f06292", "#aed581"];

export function sma(x: number[], n: number): N[] {
  const out: N[] = new Array(x.length).fill(null); if (n < 1 || x.length < n) return out; let s = 0;
  for (let i = 0; i < x.length; i++) { s += x[i]; if (i >= n) s -= x[i - n]; if (i >= n - 1) out[i] = s / n; } return out;
}
export function ema(x: N[], n: number): N[] {            // seeded with the SMA of the first n valid values
  const out: N[] = new Array(x.length).fill(null), a = 2 / (n + 1); let start = x.findIndex(v => v != null); if (start < 0 || x.length - start < n) return out;
  let e = 0; for (let i = start; i < start + n; i++) e += x[i] as number; e /= n; out[start + n - 1] = e;
  for (let i = start + n; i < x.length; i++) { e = a * (x[i] as number) + (1 - a) * e; out[i] = e; } return out;
}
export function rsi(c: number[], n: number): N[] {
  const out: N[] = new Array(c.length).fill(null); if (c.length <= n) return out; let g = 0, l = 0;
  for (let i = 1; i <= n; i++) { const d = c[i] - c[i - 1]; g += Math.max(d, 0); l += Math.max(-d, 0); } g /= n; l /= n; out[n] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
  for (let i = n + 1; i < c.length; i++) { const d = c[i] - c[i - 1]; g = (g * (n - 1) + Math.max(d, 0)) / n; l = (l * (n - 1) + Math.max(-d, 0)) / n; out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l); } return out;
}
export function atr(b: Bar[], n: number): N[] {
  const out: N[] = new Array(b.length).fill(null); if (b.length < n) return out;
  const tr = b.map((x, i) => (i === 0 ? x.high - x.low : Math.max(x.high - x.low, Math.abs(x.high - b[i - 1].close), Math.abs(x.low - b[i - 1].close))));
  let a = 0; for (let i = 0; i < n; i++) a += tr[i]; a /= n; out[n - 1] = a; for (let i = n; i < b.length; i++) { a = (a * (n - 1) + tr[i]) / n; out[i] = a; } return out;
}
export function macd(c: number[], f: number, s: number, g: number) {
  const ef = ema(c, f), es = ema(c, s), m: N[] = c.map((_, i) => (ef[i] != null && es[i] != null ? (ef[i] as number) - (es[i] as number) : null)), sig = ema(m, g);
  return { macd: m, signal: sig, hist: m.map((v, i) => (v != null && sig[i] != null ? v - (sig[i] as number) : null)) };
}
export function bollinger(c: number[], n: number, k: number) {   // population standard deviation, as most platforms
  const mid = sma(c, n), up: N[] = [], lo: N[] = [];
  c.forEach((_, i) => { if (mid[i] == null) { up.push(null); lo.push(null); return; } let v = 0; for (let j = i - n + 1; j <= i; j++) v += (c[j] - (mid[i] as number)) ** 2; const sd = Math.sqrt(v / n); up.push((mid[i] as number) + k * sd); lo.push((mid[i] as number) - k * sd); });
  return { mid, up, lo };
}
export function vwap(b: Bar[]): N[] {                            // typical price weighted by tick volume, restarted each UTC day
  let day = -1, pv = 0, v = 0; return b.map(x => { const d = Math.floor(x.time / 86400); if (d !== day) { day = d; pv = 0; v = 0; } pv += ((x.high + x.low + x.close) / 3) * x.volume; v += x.volume; return v > 0 ? pv / v : null; });
}
export function obv(b: Bar[]): N[] { let o = 0; return b.map((x, i) => { if (i > 0) o += Math.sign(x.close - b[i - 1].close) * x.volume; return o; }); }

/** series arrays for one indicator, aligned with bars (null = not enough data yet) */
export function compute(ind: Ind, b: Bar[]): N[][] {
  const c = b.map(x => x.close), p = ind.params;
  switch (ind.type) {
    case "SMA": return [sma(c, p.period)]; case "EMA": return [ema(c, p.period)];
    case "BB": { const r = bollinger(c, p.period, p.mult); return [r.up, r.mid, r.lo]; }
    case "VWAP": return [vwap(b)]; case "VOLMA": return [sma(b.map(x => x.volume), p.period)];
    case "RSI": return [rsi(c, p.period)]; case "ATR": return [atr(b, p.period)]; case "OBV": return [obv(b)];
    case "MACD": { const r = macd(c, p.fast, p.slow, p.signal); return [r.hist, r.macd, r.signal]; }
  }
}
