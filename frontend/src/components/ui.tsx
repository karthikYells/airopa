import { useEffect, useState, type ReactNode } from "react";

/** Navy header bar from the mockups (Sections 9.9 and 10.2). */
// Site links: relative on accessindia.nl, absolute when the page is served
// elsewhere (the Europe preview on the engine server sets VITE_SITE_URL).
export const SITE: string = (import.meta as any).env?.VITE_SITE_URL ?? "";

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
          <a className="flex items-center gap-3 no-underline" href={`${SITE}/`} aria-label="Access India Netherlands, home">
            <svg width="53" height="28" viewBox="0 0 110.5 58.2" aria-hidden="true">
              <path fill="currentColor" fillRule="evenodd" d="M26.9 58.1C22.8 57.7 19.7 56.9 16.4 55.3C11.5 52.9 7.7 49.6 4.8 45.1C2.2 41.3 0.7 37 0.1 32.3C-0.1 30.4 -0 26.5 0.3 24.7C1.3 18.2 4.2 12.7 8.9 8.2C11.2 6 13.4 4.4 16.2 3C19.3 1.5 22 0.7 25.4 0.2C26.9 0 30.9 -0 32.4 0.2C37.1 0.8 41.3 2.4 45.1 4.9C47 6.1 47.9 6.9 49.6 8.5C52.9 11.9 55.1 15.4 56.6 19.8C57.5 22.4 58.1 25.9 58.1 28.4C58.1 35.6 62.7 42.1 69.6 44.4C72.4 45.3 75.6 45.5 78.7 44.9C81.4 44.3 83 43.5 85.5 41.3C87.1 39.8 89.3 37.1 89.8 36.1C89.9 35.8 90 35.6 90.1 35.6C90.2 35.6 101.2 39.6 101.3 39.6C101.4 39.8 100.2 42.2 99.3 43.9C98.1 45.8 97 47.2 95 49.4C93.5 51 91.2 52.7 89 54C87.7 54.7 86.5 55.3 86.1 55.4C86 55.4 85.5 55.5 85 55.7C79.5 57.8 73.6 58.2 67.9 56.8C62.8 55.5 58.4 53 54.7 49.4C52.2 47 50.3 44.5 48.8 41.5C46.9 37.7 46 34.1 45.8 29.4C45.7 28.2 45.7 27 45.6 26.7C45.1 23.2 43.5 20.1 41.1 17.6C34.8 10.9 24.2 10.7 17.6 17C12.2 22.1 10.8 29.9 14 36.5C15.6 39.8 18.5 42.7 21.9 44.3C23.2 44.9 24.5 45.3 25.9 45.6C27.5 46 30.6 46 32.1 45.6C37.1 44.6 41.2 41.7 43.7 37.2L44.2 36.4L44.4 37.4C45.4 41 47.4 45 49.8 48.1L50.4 48.8L49.5 49.7C44.9 54.5 38.3 57.5 31.5 58.1C30.4 58.2 27.7 58.2 26.9 58.1ZM89.3 21.3C88.7 20.2 88 19.3 86.6 17.9C85 16.4 83.8 15.5 82.4 14.8C79 13.1 75.3 12.6 71.5 13.4C66.8 14.4 62.9 17.2 60.3 21.6C60.2 21.8 60.1 21.9 60.1 21.8C60 21.7 59.9 21.1 59.7 20.4C58.6 16.9 56.8 13.4 54.5 10.4L54 9.8L55.1 8.7C59.4 4.5 65.4 1.8 71.7 1C73 0.8 76.9 0.8 78.2 1C80.6 1.3 83.7 2 85.5 2.8C85.9 3 86.2 3.1 86.2 3C86.3 3 87.6 3.6 88.7 4.2C91 5.4 93.3 7.2 95.2 9.1C96.9 10.7 97.6 11.6 98.8 13.5C99.7 14.9 101.3 18.1 101.3 18.4C101.3 18.5 101.5 18.4 95 20.5C92.2 21.3 89.9 22.1 89.8 22.1C89.8 22.1 89.5 21.8 89.3 21.3Z" />
              <path fill="#E8791C" fillRule="evenodd" d="M72.4 39.2C68.1 38.4 64.9 35 64.4 30.6C64.1 27.8 65.2 24.7 67.3 22.6C70.5 19.5 75.4 18.9 79.2 21.3C80.3 22 81.1 22.6 82.1 23.9C83.7 25.8 85.9 27.3 88.5 28.2C90.6 28.9 93.3 28.6 96 27.3C97.1 26.7 97.8 26.2 98.9 25.2C100 24.1 100.6 23.7 101.5 23.4C105.9 21.7 110.5 25 110.5 29.6C110.5 30.8 110.3 31.5 109.8 32.6C109.5 33.3 109.2 33.6 108.5 34.3C107.2 35.6 105.8 36.2 103.9 36.2C102.4 36.2 101 35.7 99.6 34.6C97.4 33 95.5 32.1 93 31.4C90.7 30.8 88 31.2 85.5 32.6C84 33.4 83.3 34 81.4 36.1C80.2 37.5 78.4 38.6 76.5 39.1C75.3 39.4 73.5 39.5 72.4 39.2Z" />
            </svg>
            <span className="font-display text-[19px] font-bold tracking-tight">
              Access India <span className="text-orange">Netherlands</span>
            </span>
          </a>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-[15px]">
            {links.map(([href, label]) => (
              <a key={href} href={href.startsWith("/") ? SITE + href : href}
                 className={`no-underline hover:text-band-fg ${label === "Engines" ? "text-band-fg" : "text-band-muted"}`}>
                {label}
              </a>
            ))}
          </div>
        </nav>
        <div className="max-w-[46em] pb-12 pt-7">
          <div className="font-mono text-[12.5px] uppercase tracking-[0.12em] text-orange">
            <a href={`${SITE}/engines/`} className="no-underline">Engines</a> / {crumb}
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
        <span>© 2026 Access India Initiative (AII) Netherlands · <a className="text-band-fg" href={`${SITE}/privacy/`}>Privacy</a></span>
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
