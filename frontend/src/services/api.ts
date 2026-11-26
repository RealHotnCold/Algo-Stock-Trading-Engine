export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };
export type Tick = { ok: true; symbol: string; bid: number; ask: number; last: number; spread_points: number; time: number; digits: number; market_open: boolean } | { ok: false; reason: string };
export type Status = { connected: boolean; reason?: string; demo_only: boolean; trading_allowed: boolean; trading_reason: string;
  account?: { login: number; server: string; broker: string; currency: string; kind: string; balance: number; equity: number; margin: number; margin_free: number; leverage: number } };

export async function call<T>(url: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(url, { method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) { const d = (await r.json().catch(() => ({}))).detail; throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : r.statusText); }
  return r.json();
}
const get = <T,>(url: string) => call<T>(url);
export type Check = { name: string; passed: boolean; detail: string };
export type Validation = { stage: string; approved: boolean; reason?: string | null; risk?: { approved: boolean; checks: Check[] } };
export type OrderIn = { symbol: string; side: "buy" | "sell"; volume: number; order_type: string; price?: number | null; sl?: number | null; tp?: number | null };
export type Execution = Validation & { executed: boolean; state?: string; result?: { price: number; retcode: number }; latency_exec_ms?: number };
export type Position = { ticket: number; symbol: string; side: string; volume: number; price_open: number; sl: number; tp: number; profit: number };
export type Signal = { regime: string; decision: string; target_position: number; confidence: number; threshold: number; abstain_reason: string; memory_neighbors: number;
  agents: { agent: string; action: string; confidence: number; base_weight: number; memory_outcome_bps: number; rationale: string }[];
  data_source: string; latency_infer_ms: number; note: string };
export type RiskCfg = Record<string, number | boolean | null | number[]>;
export type BtResult = { metrics: Record<string, number | null>; out_of_sample: boolean; period: string; start: number; end: number; bars: number; spread_source: string; assumptions: string;
  curve: { time: number; equity: number }[]; trades: { entry_time: number; exit_time: number; side: string; lots: number; entry: number; exit: number; pnl: number; reason: string }[]; n_trades_total: number; runtime_s: number };
export type Drawing = { id: string; type: "hline" | "support" | "resistance" | "trend" | "alert"; price?: number; t1?: number; p1?: number; t2?: number; p2?: number; dir?: "above" | "below"; triggered?: boolean };
export const api = {
  autoPreview: (p: unknown) => call<any>("/api/auto/preview", "POST", p),
  autoStatus: () => get<any>("/api/auto/status"), autoStart: (p: unknown) => call<any>("/api/auto/start", "POST", p), autoStop: (closePositions: boolean) => call<any>(`/api/auto/stop?close_positions=${closePositions}`, "POST"),
  drawings: (symbol: string, tf: string) => get<{ items: Drawing[] }>(`/api/drawings?symbol=${encodeURIComponent(symbol)}&tf=${tf}`),
  saveDrawings: (symbol: string, tf: string, items: Drawing[]) => call<{ items: Drawing[] }>(`/api/drawings?symbol=${encodeURIComponent(symbol)}&tf=${tf}`, "PUT", { items }),
  settings: () => get<any>("/api/settings"), setRisk: (p: unknown) => call<any>("/api/risk/config", "PUT", p), reconnect: () => call<Status>("/api/mt5/reconnect", "POST"),
  portfolio: (days = 90) => get<any>(`/api/portfolio?days=${days}`),
  trades: (days = 365) => get<any>(`/api/trades?days=${days}`),
  histVol: (symbol: string, tf: string) => get<{ last_close: number; annual_vol: number; bars: number }>(`/api/sim/hist-vol?symbol=${symbol}&tf=${tf}`),
  mc: (p: unknown) => call<any>("/api/sim/montecarlo", "POST", p), bs: (p: unknown) => call<any>("/api/sim/blackscholes", "POST", p),
  replay: (p: unknown) => call<any>("/api/sim/replay", "POST", p), scenario: (p: unknown) => call<any>("/api/sim/scenario", "POST", p),
  backtest: (p: Record<string, unknown>) => call<BtResult>("/api/backtest", "POST", p),
  positions: () => get<Position[]>("/api/positions"),
  close: (t: number) => call<{ closed: boolean; result: { comment: string } }>(`/api/positions/${t}/close`, "POST"),
  validate: (o: OrderIn) => call<Validation>("/api/orders/validate", "POST", o),
  submit: (o: OrderIn) => call<Execution>("/api/orders", "POST", o),
  size: (symbol: string, side: string, sl: number) => call<{ volume: number; entry: number }>("/api/orders/size", "POST", { symbol, side, sl }),
  risk: () => get<RiskCfg>("/api/risk/config"),
  signal: (symbol: string, tf = "M5") => get<Signal>(`/api/strategy/signal?symbol=${encodeURIComponent(symbol)}&tf=${tf}`),
  comparison: () => get<any>("/api/strategy/comparison"),
  walkforward: () => get<any>("/api/strategy/walkforward"),
  results: () => get<any>("/api/strategy/results"),
  status: () => get<Status>("/api/status"),
  timeframes: () => get<string[]>("/api/timeframes"),
  symbols: () => get<{ source: "mt5" | "stored"; symbols: { name: string; description?: string }[] }>("/api/symbols"),
  bars: (symbol: string, tf: string, count = 1500) => get<{ source: "mt5" | "stored"; bars: Bar[] }>(`/api/bars?symbol=${encodeURIComponent(symbol)}&tf=${tf}&count=${count}`),
};
export function openTicks(symbol: string, onTick: (t: Tick) => void) {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/ticks?symbol=${encodeURIComponent(symbol)}`);
  ws.onmessage = (e) => onTick(JSON.parse(e.data));
  return () => ws.close();
}
