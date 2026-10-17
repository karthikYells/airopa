import { useEffect, useState } from "react";
import { copyToNetlifyForms, getExamples, requestReport, scoreCompany } from "../api";
import type { Market, OwnEvidence, PeerHeadline, ScoreBlock, Snapshot } from "../types";
import {
  DomainInput, Rich, Scanning, SiteFooter, SiteHeader, bandStyle, companyFromUrl, setCompanyInUrl,
} from "./ui";

/** The public India Market Assessment, an engine page on accessindia.nl.
 *  Content follows the Section 9.9 mockup; styling follows the site. */
export function PublicPage() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [examples, setExamples] = useState<string[]>([]);
  const [domain, setDomain] = useState("");

  useEffect(() => {
    getExamples().then(setExamples);
    const shared = companyFromUrl();
    if (shared) run(shared);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (url: string) => {
    setDomain(url);
    setCompanyInUrl(url);
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await scoreCompany(url));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <SiteHeader
        crumb="India Market Assessment"
        title="Is India a market for what you sell,"
        accent="and are you ready to win it?"
        intro="Enter your company website. From public sources, see how India's demand, policy and route to market line up with what your company sells, and where you stand in India today. Free, no login. Get the report as a PDF in your inbox."
      />
      <main className="mx-auto max-w-[1180px] space-y-6 px-4 pt-10 sm:px-10">
        <DomainInput
          initial={domain}
          button="Check my company"
          loading={loading}
          onSubmit={run}
          placeholder="yourcompany.com"
          hint="We read public company websites, registries and people data. Nothing is asked of you."
        />

        {error && <p className="text-sm text-red">{error}</p>}
        {loading && <Scanning />}

        {!data && !loading && examples.length > 0 && (
          <p className="text-sm text-mute">
            Or see an illustrative example:{" "}
            {examples.slice(0, 3).map((d, i) => (
              <span key={d}>
                {i > 0 && " · "}
                <button onClick={() => run(d)} className="font-mono text-orange-ink underline">
                  {d}
                </button>
              </span>
            ))}
          </p>
        )}

        {data && <SnapshotBody data={data} />}
      </main>
      <SiteFooter />
    </>
  );
}

function SnapshotBody({ data }: { data: Snapshot }) {
  const hasScores = !!(data.technology_hub || data.indicative_scale);
  return (
    <>
      {data.company && <CompanyBar data={data} />}

      {data.mode === "REJECTED" && <Notice title="Please enter a company website" body={data.message} />}
      {data.mode === "EXCLUDED" && data.content && <Notice title={data.content.headline} body={data.content.body} />}
      {data.mode === "INSUFFICIENT_DATA" && <Insufficient data={data} />}

      {/* 1. Selling into India */}
      {data.market && <MarketSection m={data.market} />}

      {/* 2. Your India presence today */}
      {(data.india_status || data.peer_headline || data.own_evidence?.length) && (
        <section className="space-y-5">
          <SectionLabel>Your India presence today</SectionLabel>
          {data.india_status && (
            <p className="text-[clamp(20px,2.4vw,26px)] font-display font-bold leading-snug text-ink">
              {data.india_status}
            </p>
          )}
          {data.message && data.mode !== "INSUFFICIENT_DATA" && data.mode !== "REJECTED" && (
            <p className="rounded-panel border-l-4 border-orange bg-orange-soft px-5 py-3 text-[15px] text-ink">
              {data.message}
            </p>
          )}
          {data.peer_headline && <PeerCard peer={data.peer_headline} />}
          {data.own_evidence && data.own_evidence.length > 0 && (
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              {data.own_evidence.map((p) => <EvidenceCard key={p.title} p={p} />)}
            </div>
          )}
        </section>
      )}

      {hasScores && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {data.technology_hub && <ScoreCard s={data.technology_hub} accent="green" />}
          {data.indicative_scale && <ScaleCard scale={data.indicative_scale} />}
        </div>
      )}

      {data.run_id && data.mode !== "REJECTED" && data.mode !== "EXCLUDED" && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.1fr]">
          {data.withheld ? <Withheld items={data.withheld} /> : <BusinessCaseNote data={data} />}
          <ReportForm data={data} />
        </div>
      )}

      {data.disclaimer && (
        <p className="border-t border-line pt-4 text-[13px] leading-5 text-mute">{data.disclaimer}</p>
      )}
    </>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-mono text-[12.5px] font-medium uppercase tracking-[0.12em] text-orange-ink">
      {children}
    </h2>
  );
}

const levelStyle = (level: string) =>
  level === "Very strong" ? "bg-green/10 text-green"
    : level === "Strong" ? "bg-orange-soft text-orange-ink"
      : level === "Moderate" ? "bg-amber/10 text-amber" : "bg-red/10 text-red";

/** India as a market for what they sell: the lead block of the page. */
function MarketSection({ m }: { m: Market }) {
  return (
    <section className="space-y-4">
      <SectionLabel>India as a market for what you sell</SectionLabel>
      <div className="rounded-panel border border-line border-l-4 border-l-orange bg-white p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-8">
          <div className="whitespace-nowrap">
            <span className="font-display text-6xl font-extrabold text-orange">{m.score}</span>
            <span className="ml-1 font-mono text-sm text-mute">/ 100</span>
          </div>
          <div>
            <p className="font-display text-[clamp(22px,2.6vw,30px)] font-extrabold leading-tight text-ink">{m.headline}</p>
            <p className="mt-1 text-sm text-mute">
              {m.label}: <strong className="text-ink">{m.band}</strong> · indicative
            </p>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
          {m.dimensions.map((d) => (
            <div key={d.name} className="border-t border-line pt-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-[16px] font-bold text-ink">{d.name}</h3>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 font-mono text-[11px] uppercase ${levelStyle(d.level)}`}>
                  {d.level}
                </span>
              </div>
              <p className="mt-1 text-[15px] text-mute">{d.insight}</p>
            </div>
          ))}
        </div>
        <p className="mt-5 text-xs text-mute">{m.basis}</p>
      </div>
    </section>
  );
}

function PeerCard({ peer }: { peer: PeerHeadline }) {
  return (
    <section className="flex flex-col gap-4 rounded-panel border border-line border-l-4 border-l-orange bg-white px-6 py-5 sm:flex-row sm:items-center sm:gap-8">
      <div className="whitespace-nowrap font-display text-5xl font-extrabold text-orange sm:text-6xl">
        {peer.with_centre} of {peer.total}
      </div>
      <div>
        <h2 className="text-xl font-bold text-ink">
          of the companies we identify as your closest peers already run a capability centre in India.
        </h2>
        <p className="mt-1 text-[15px] text-mute">
          {peer.recent_24m ? `${peer.recent_24m} of them opened within the last 24 months. ` : ""}
          Your cohort: <strong className="text-ink">{peer.cohort_definition}</strong>.
          {peer.aggregate_india_headcount
            ? ` Together those centres employ over ${peer.aggregate_india_headcount.toLocaleString()} people.`
            : ""}
        </p>
      </div>
    </section>
  );
}

function CompanyBar({ data }: { data: Snapshot }) {
  const c = data.company!;
  const facts = [c.sector, c.country, c.revenue, c.headcount].filter(Boolean) as string[];
  return (
    <section className="flex flex-col gap-2 rounded-panel border border-line bg-white px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-[clamp(24px,3vw,32px)] font-extrabold tracking-tight text-ink">{c.name || c.input}</h2>
        <p className="text-[15px] text-mute">{facts.join("  ·  ")}</p>
      </div>
    </section>
  );
}

function ScoreCard({ s, accent }: { s: ScoreBlock; accent: "orange" | "green" }) {
  const color = accent === "orange" ? "text-orange" : "text-green";
  const bar = accent === "orange" ? "bg-orange" : "bg-green";
  return (
    <section className="rounded-panel border border-line bg-white p-6">
      <h3 className="text-[21px] font-bold text-ink">{s.label}</h3>
      {s.question && <p className="mt-0.5 text-sm text-mute">{s.question}</p>}
      <div className="mt-5 flex items-end justify-between">
        <p>
          <span className={`font-display text-5xl font-extrabold ${color}`}>{s.score}</span>
          <span className="ml-1 font-mono text-sm text-mute">/ 100</span>
        </p>
        <span className={`rounded-full px-2.5 py-1 font-mono text-[11px] uppercase ${bandStyle(s.band)}`}>{s.band}</span>
      </div>
      <div className="mt-3 h-2 w-full rounded-full bg-line">
        <div className={`h-2 rounded-full ${bar}`} style={{ width: `${s.score}%` }} />
      </div>
      <dl className="mt-4 space-y-1.5 text-sm">
        {s.sub_dimensions.map((d) => (
          <div key={d.name} className="flex justify-between">
            <dt className="text-mute">{d.name}</dt>
            <dd className="font-semibold text-ink">{d.level}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-mute">Evidence coverage {s.coverage}%</p>
    </section>
  );
}

function ScaleCard({ scale }: { scale: NonNullable<Snapshot["indicative_scale"]> }) {
  const kv = (k: string, v: string, sub?: string) => (
    <div className="mt-4">
      <p className="text-[13.5px] text-band-muted">{k}</p>
      <p className="font-display text-2xl font-bold text-orange">{v}</p>
      {sub && <p className="text-xs text-band-muted">{sub}</p>}
    </div>
  );
  return (
    <section className="rounded-panel bg-navy p-6 text-band-fg">
      <h3 className="text-[21px] font-bold">Indicative scale, if you moved</h3>
      <p className="mt-0.5 text-sm text-band-muted">{scale.note}</p>
      {kv("First phase team", scale.first_phase_team)}
      {kv("Indicative run-rate saving", scale.indicative_saving, scale.saving_basis)}
      {kv("Time to first team live", scale.time_to_first_team_live)}
    </section>
  );
}

function EvidenceCard({ p }: { p: OwnEvidence }) {
  const dot = p.tone === "red" ? "bg-red" : p.tone === "orange" ? "bg-orange" : "bg-[#2F6FD0]";
  return (
    <section className="rounded-panel border border-line bg-white p-6">
      <h3 className="flex items-center gap-2 text-[17px] font-bold text-ink">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} />
        {p.title}
      </h3>
      <ul className="mt-3 space-y-2 text-[15px] text-mute">
        {p.bullets.map((b) => (
          <li key={b} className="grid grid-cols-[14px_1fr] gap-1.5">
            <span className="text-orange-ink">•</span>
            <span><Rich text={b} /></span>
          </li>
        ))}
      </ul>
      {p.as_of && <p className="mt-3 font-mono text-[11px] text-mute">Source dated {p.as_of}</p>}
    </section>
  );
}

function Withheld({ items }: { items: string[] }) {
  return (
    <section className="rounded-panel border border-dashed border-mute/40 bg-white p-6">
      <h3 className="text-[21px] font-bold text-ink">What this assessment deliberately does not show you</h3>
      <p className="mt-1 text-sm text-mute">
        These need judgement and verification, not automation. They are what the full business case
        contains, built by Airopa Global in two weeks, at no obligation.
      </p>
      <ul className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2.5 text-[15px] text-ink sm:grid-cols-2">
        {items.map((w) => (
          <li key={w} className="grid grid-cols-[14px_1fr] gap-1.5">
            <span className="font-mono text-orange-ink">+</span>
            {w}
          </li>
        ))}
      </ul>
    </section>
  );
}

function BusinessCaseNote({ data }: { data: Snapshot }) {
  return (
    <section className="rounded-panel border border-line bg-white p-6">
      <h3 className="text-[21px] font-bold text-ink">
        {data.lead_capture?.title ?? "Want the full picture?"}
      </h3>
      <p className="mt-2 text-[15px] text-mute">
        {data.lead_capture?.offer ??
          "Airopa Global builds a full business case against your own estate and peer group in two weeks, at no obligation."}
      </p>
    </section>
  );
}

const ROLES = ["CEO / Founder", "CFO / Finance", "CTO / CIO / Technology", "COO / Operations",
  "HR / People", "Strategy / Business development", "Other"];

/** "Email me the report": same fields, rules and wording as the GCC Business
 *  Case engine. The engine saves the lead and emails the PDF of this snapshot. */
function ReportForm({ data }: { data: Snapshot }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState(data.company?.name ?? "");
  const [role, setRole] = useState("");
  const [call, setCall] = useState(false);
  const [bot, setBot] = useState("");
  const [allowPersonal, setAllowPersonal] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [askPersonal, setAskPersonal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    if (!name.trim() || !company.trim()) { setMsg("Please fill in your name and company."); return; }
    setBusy(true);
    try {
      const status = await requestReport({
        run_id: data.run_id!, snapshot_token: data.snapshot_token ?? "",
        name: name.trim(), email: email.trim(), company: company.trim(),
        role, call_partner: call, allow_personal: allowPersonal, bot_field: bot,
      });
      void copyToNetlifyForms({
        "bot-field": bot, name: name.trim(), email: email.trim(), company: company.trim(), role,
        call_partner: call ? "yes" : "no", email_type: allowPersonal ? "personal" : "work",
        domain: data.company?.input ?? "", snapshot_link: window.location.href,
      });
      const safeEmail = email.trim();
      setDone(status === "sent"
        ? `Report sent to ${safeEmail}. It should arrive within a few minutes; if not, please check your spam folder.`
        : `Thank you, ${name.trim()}. We'll email your report to ${safeEmail} within one business day.`);
    } catch (err) {
      const r = (err as Error).message;
      if (r === "personal_email") {
        setMsg("Please use your work email so we can tailor the report to your company.");
        setAskPersonal(true);
      } else if (r === "invalid_email") {
        setMsg("That email address doesn't look right. Please check it.");
      } else if (r === "rate_limited") {
        setMsg("You have requested several reports in a short time. Please try again later.");
      } else {
        setMsg("Something went wrong. Please try again, or email accessindia@airopa.co.");
      }
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-[10px] border border-line bg-white px-3 py-2.5 text-[15px] text-ink outline-none focus:border-orange";
  return (
    <section className="rounded-panel border border-line border-l-4 border-l-orange bg-white p-6">
      <div className="font-mono text-[12.5px] uppercase tracking-[0.12em] text-orange-ink">Free report</div>
      <h3 className="mt-1 text-[21px] font-bold text-ink">Get this assessment in your inbox</h3>
      <p className="mt-1 text-[15px] text-mute">
        A PDF of your India Market Assessment: India as a market for what you sell, where you stand in
        India today, and what the full business case would add. Ready to forward to your board.
      </p>
      {done ? (
        <p className="mt-5 rounded-[10px] bg-orange-soft px-4 py-3 text-[15px] text-ink" role="status">{done}</p>
      ) : (
        <form onSubmit={submit} noValidate className="mt-4">
          <p className="absolute left-[-9999px]" aria-hidden="true">
            <label>Leave this empty <input tabIndex={-1} autoComplete="off" value={bot} onChange={(e) => setBot(e.target.value)} /></label>
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="text-sm text-mute">Full name
              <input className={field} autoComplete="name" maxLength={80} required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="text-sm text-mute">Work email
              <input className={field} type="email" autoComplete="email" maxLength={254} required value={email}
                     onChange={(e) => { setEmail(e.target.value); setAllowPersonal(false); setAskPersonal(false); }} />
            </label>
            <label className="text-sm text-mute">Company
              <input className={field} autoComplete="organization" maxLength={80} required value={company} onChange={(e) => setCompany(e.target.value)} />
            </label>
            <label className="text-sm text-mute">Role <em>(optional)</em>
              <select className={field} value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="">Select…</option>
                {ROLES.map((r) => <option key={r}>{r}</option>)}
              </select>
            </label>
          </div>
          {msg && (
            <p className="mt-3 text-sm text-red" role="alert">
              {msg}{" "}
              {askPersonal && !allowPersonal && (
                <button type="button" className="underline" onClick={() => { setAllowPersonal(true); setMsg("OK, submit again to use this address."); }}>
                  I don't have a work email
                </button>
              )}
            </p>
          )}
          <label className="mt-4 flex gap-2.5 text-sm text-ink">
            <input type="checkbox" className="mt-1 accent-[#E8791C]" checked={call} onChange={(e) => setCall(e.target.checked)} />
            <span>I'd also like a free 30-minute call with Access India's GCC partner, Airopa Global. I agree to my details being shared with Airopa Global for this purpose.</span>
          </label>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <button type="submit" disabled={busy}
                    className="rounded-full bg-orange px-5 py-3 text-[15.5px] font-semibold text-[#16120D] transition hover:-translate-y-px disabled:opacity-60">
              {busy ? "Sending…" : "Email me the report"}
            </button>
          </div>
          <p className="mt-3 text-xs text-mute">
            Your report is sent by our partner Airopa Global from accessindia@airopa.co. We use your details only to
            send this report and, if you ticked the box, to arrange the call.{" "}
            <a href="/privacy/" target="_blank" rel="noreferrer">Privacy notice</a>
          </p>
        </form>
      )}
    </section>
  );
}

function Insufficient({ data }: { data: Snapshot }) {
  return (
    <section className="rounded-panel border border-line bg-white p-6">
      <h3 className="text-[21px] font-bold text-ink">{data.message}</h3>
      <p className="mt-2 text-[15px] text-mute">
        We publish only what we can verify, and found {data.verified_count} verified data points, not enough
        for an honest assessment. Tell us a few facts and we complete the picture for you.
      </p>
      {data.ask && (
        <ul className="mt-3 space-y-1.5 text-[15px] text-ink">
          {data.ask.map((a) => (
            <li key={a} className="grid grid-cols-[14px_1fr] gap-1.5">
              <span className="font-mono text-orange-ink">+</span>{a}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Notice({ title, body }: { title?: string; body?: string }) {
  return (
    <section className="rounded-panel border border-line bg-white p-6">
      <h3 className="text-[21px] font-bold text-ink">{title}</h3>
      {body && <p className="mt-2 text-mute">{body}</p>}
    </section>
  );
}
