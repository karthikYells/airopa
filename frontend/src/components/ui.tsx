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

/** accessindia.nl site header: band, nav and page head, as on the other engines. */
export function SiteHeader({ crumb, title, accent, intro }: {
  crumb: string; title: string; accent: string; intro: string;
}) {
  const links: [string, string][] = [
    ["/#corridor", "The corridor"], ["/#offer", "What we do"], ["/#who", "Who it's for"],
    ["/engines/", "Engines"], ["/blog/", "Insights"], ["/#about", "About"],
  ];
  return (
    <div className="bg-navy text-band-fg">
      <div className="mx-auto max-w-[1180px] px-4 sm:px-10">
        <nav className="flex flex-wrap items-center justify-between gap-4 py-5" aria-label="Main">
          <a className="flex items-center gap-3 no-underline" href="/" aria-label="Access India Netherlands, home">
            <svg width="44" height="30" viewBox="0 0 44 30" aria-hidden="true">
              <path d="M17 6.5a9 9 0 1 0 0 17" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
              <path d="M37 6.5a9 9 0 1 0 0 17" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
              <circle cx="38" cy="15" r="4" fill="#E8791C" />
            </svg>
            <span className="font-display text-[19px] font-bold tracking-tight">
              Access India <span className="text-orange">Netherlands</span>
            </span>
          </a>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-[15px]">
            {links.map(([href, label]) => (
              <a key={href} href={href}
                 className={`no-underline hover:text-band-fg ${label === "Engines" ? "text-band-fg" : "text-band-muted"}`}>
                {label}
              </a>
            ))}
          </div>
        </nav>
        <div className="max-w-[46em] pb-12 pt-7">
          <div className="font-mono text-[12.5px] uppercase tracking-[0.12em] text-orange">
            <a href="/engines/" className="no-underline">Engines</a> / {crumb}
          </div>
          <h1 className="mt-4 text-[clamp(34px,5vw,56px)] font-extrabold leading-[1.08] tracking-[-0.025em]">
            {title} <span className="text-orange">{accent}</span>
          </h1>
          <p className="mt-5 text-[18.5px] text-band-muted">{intro}</p>
        </div>
      </div>
    </div>
  );
}

export function SiteFooter() {
  return (
    <div className="mt-24 bg-navy">
      <footer className="mx-auto flex max-w-[1180px] flex-wrap justify-between gap-4 px-4 py-6 text-sm text-band-muted sm:px-10">
        <span>© 2026 Access India Initiative (AII) Netherlands · <a className="text-band-fg" href="/privacy/">Privacy</a></span>
        <span>Eindhoven · Founding partner <a className="text-band-fg" href="https://www.airopa.co" target="_blank" rel="noopener">Airopa Global</a></span>
      </footer>
    </div>
  );
}

/** Domain input with the action button. */
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
        className="flex flex-col gap-2 rounded-panel border border-line bg-white p-2 sm:flex-row sm:items-center"
      >
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={placeholder}
          disabled={loading}
          aria-label="Company website"
          className="min-w-0 flex-1 rounded-full px-4 py-3 font-mono text-base font-medium text-ink outline-none placeholder:font-normal placeholder:text-mute/60"
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="rounded-full bg-orange px-6 py-3 text-[15.5px] font-semibold text-[#16120D] transition hover:-translate-y-px disabled:opacity-60"
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
