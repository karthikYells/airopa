import type { InternalBrief, Snapshot } from "./types";

// Same-origin in production (served behind the same domain or a /api proxy).
// Override with VITE_API_BASE if the backend lives elsewhere.
const BASE = (import.meta as any).env?.VITE_API_BASE ?? "";

export async function scoreCompany(url: string): Promise<Snapshot> {
  const res = await fetch(`${BASE}/api/score`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

export async function assessCompany(url: string): Promise<InternalBrief> {
  const res = await fetch(`${BASE}/api/assess`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

export async function getExamples(): Promise<string[]> {
  try {
    const res = await fetch(`${BASE}/api/examples`);
    if (!res.ok) return [];
    return (await res.json()).domains ?? [];
  } catch {
    return [];
  }
}
