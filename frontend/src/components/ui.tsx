import { useEffect, useState, type ReactNode } from "react";

/** Navy header bar from the mockups (Sections 9.9 and 10.2). */
export function TopBar({ title, right }: { title: string; right: ReactNode }) {
  return (
    <header className="bg-navy px-5 py-4 text-white sm:px-9">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/70">
            Airopa Global
          </p>
          <p className="mt-1 text-lg font-bold">{title}</p>
        </div>
        <div className="text-right text-xs leading-5 text-white/80">{right}</div>
      </div>
    </header>
  );
}

/** Domain input with the navy action button. */
export function DomainInput({
  initial = "",
  placeholder = "yourcompany.com",
  button,
  loading,
  onSubmit,
  hint,
}: {
  initial?: string;
  placeholder?: string;
  button: string;
  loading: boolean;
  onSubmit: (url: string) => void;
  hint?: string;
}) {
  const [url, setUrl] = useState(initial);
  useEffect(() => setUrl(initial), [initial]);
  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) onSubmit(url.trim());
        }}
        className="flex flex-col overflow-hidden rounded-md border-2 border-navy bg-white sm:flex-row"
      >
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={placeholder}
          disabled={loading}
          className="min-w-0 flex-1 px-4 py-3 font-mono text-base font-semibold text-ink outline-none placeholder:font-normal placeholder:text-mute/60"
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="bg-navy px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#162a4d] disabled:opacity-60"
        >
          {loading ? "Assessing…" : `${button} →`}
        </button>
      </form>
      {hint && <p className="mt-2 text-xs text-mute">{hint}</p>}
    </div>
  );
}

/** The company in the address bar (?company=…), so a snapshot can be shared
 *  and reopened (Section 9.5: every snapshot gets a shareable URL). */
export function companyFromUrl(): string {
  try {
    return new URLSearchParams(window.location.search).get("company") ?? "";
  } catch {
    return "";
  }
}

export function setCompanyInUrl(company: string) {
  try {
    const p = new URLSearchParams(window.location.search);
    p.set("company", company);
    window.history.replaceState(null, "", `${window.location.pathname}?${p.toString()}`);
  } catch {
    /* address bar not writable (sandboxed preview) */
  }
}

/** Renders **bold** spans inside generated evidence text. */
export function Rich({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i} className="font-semibold text-ink">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

export const bandStyle = (band: string) =>
  band === "Very strong"
    ? "bg-green/10 text-green"
    : band === "Strong"
      ? "bg-orange/10 text-orange"
      : band === "Moderate"
        ? "bg-amber/10 text-amber"
        : "bg-red/10 text-red";

/** Pulsing progress lines while the engine runs (about 90 seconds, Section 9). */
export function Scanning() {
  const steps = [
    "Resolving the company",
    "Checking India presence",
    "Gathering public signals",
    "Scoring against the reference data",
    "Composing your snapshot",
  ];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((n) => Math.min(n + 1, steps.length - 1)), 4000);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <div className="mt-6 rounded-md border border-line bg-white p-5">
      {steps.map((s, n) => (
        <div key={s} className="flex items-center gap-3 py-1 text-sm">
          <span
            className={`h-2 w-2 rounded-full ${
              n < i ? "bg-green" : n === i ? "animate-pulse bg-orange" : "bg-line"
            }`}
          />
          <span className={n <= i ? "text-ink" : "text-mute/60"}>{s}</span>
        </div>
      ))}
    </div>
  );
}
