import type { InternalBrief, Snapshot } from "./types";

// Where the engine API lives. Locally the Vite dev server proxies /api to the
// backend. On accessindia.nl set VITE_API_BASE to the engine's own address
// (e.g. https://engine.accessindia.nl): a run takes 10-60 seconds, longer than
// Netlify's proxy allows, so the page calls the engine directly.
const BASE = (import.meta as any).env?.VITE_API_BASE ?? "";

export async function scoreCompany(url: string): Promise<Snapshot> {
  const res = await fetch(`${BASE}/api/score`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (res.status === 429) throw new Error("You have run several checks in a short time. Please try again in an hour.");
  if (!res.ok) throw new Error(`Something went wrong (${res.status}). Please try again.`);
  return res.json();
}

export interface ReportRequest {
  run_id: string;
  snapshot_token: string;
  name: string;
  email: string;
  company: string;
  role: string;
  call_partner: boolean;
  allow_personal: boolean;
  bot_field: string;
}

/** Ask the engine to email the PDF. Returns "sent" or "queued", or throws
 *  with the engine's reason (invalid_email, personal_email, ...). */
export async function requestReport(path: string, body: ReportRequest): Promise<"sent" | "queued"> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 429) throw new Error("rate_limited");
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({})))?.detail;
    throw new Error(typeof detail === "string" ? detail : "error");
  }
  return (await res.json()).status;
}

/** Best-effort copy of the lead to Netlify Forms (only works on accessindia.nl). */
export async function copyToNetlifyForms(fields: Record<string, string>,
                                         formName = "india-market-assessment-report"): Promise<void> {
  try {
    await fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ "form-name": formName, ...fields }).toString(),
    });
  } catch {
    /* not on Netlify (local dev): the engine keeps its own copy */
  }
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

/** Europe Market Assessment: assess an Indian company's website. */
export async function scoreEurope(url: string): Promise<Snapshot> {
  const res = await fetch(`${BASE}/api/europe/score`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (res.status === 429) throw new Error("You have run several checks in a short time. Please try again in an hour.");
  if (!res.ok) throw new Error(`Something went wrong (${res.status}). Please try again.`);
  return res.json();
}
