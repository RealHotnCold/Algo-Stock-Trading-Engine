import { api, call } from "./api";
let cache: any = null;
export const cached = () => cache;
export async function loadSettings() { if (!cache) cache = await api.settings(); return cache; }
export async function saveSettings(partial: unknown) { cache = await call<any>("/api/settings", "PUT", partial); return cache; }
