import { useEffect, useState } from "react";
import { getExamples, scoreCompany } from "../api";
import type { OwnEvidence, PeerHeadline, ScoreBlock, Snapshot } from "../types";
import { DomainInput, Rich, Scanning, TopBar, bandStyle, companyFromUrl, setCompanyInUrl } from "./ui";

/** The public self-serve snapshot, laid out as the Section 9.9 mockup. */
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
    <div className="mx-auto max-w-6xl bg-white shadow-sm">
      <TopBar
        title="India Opportunity Snapshot"
        right={
          <>
            <div>Free · No login · Generated from public information</div>
            <div>Full business case delivered in 2 weeks</div>
          </>
        }
      />
      <main className="space-y-6 px-5 py-6 sm:px-9">
        <DomainInput
          initial={domain}
          button="Assess my company"
          loading={loading}
          onSubmit={run}
          hint="Enter your company website. We read public company websites, registries and people data. Nothing is asked of you."
        />

        {error && <p className="text-sm text-red">{error}</p>}
        {loading && <Scanning />}

        {!data && !loading && <Intro examples={examples} onPick={run} />}

        {data && <SnapshotBody data={data} />}
      </main>
    </div>
  );
}

function Intro({ examples, onPick }: { examples: string[]; onPick: (d: string) => void }) {
  return (
    <section className="rounded-md border border-line bg-panel/60 px-6 py-8">
      <h1 className="text-2xl font-bold text-navy sm:text-3xl">
        See your India capability centre opportunity in about 90 seconds.
      </h1>
      <p className="mt-3 max-w-3xl text-mute">
        We assess, from public sources alone, whether India can supply the talent you need
        and whether it is a market for what you sell. Everything shown is about your own
        company. Unverified figures are left out, never estimated.
      </p>
      {examples.length > 0 && (
        <div className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-mute">
            Or try an illustrative example
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {examples.map((d) => (
              <button
                key={d}
                onClick={() => onPick(d)}
                className="rounded-full border border-line bg-white px-3 py-1.5 font-mono text-sm text-ink hover:border-navy hover:text-navy"
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function SnapshotBody({ data }: { data: Snapshot }) {
  const full = data.mode === "STANDARD" || data.mode === "EXISTING_CENTRE";
  const hasScores = !!(data.india_market || data.technology_hub || data.indicative_scale);
  return (
    <>
      {data.peer_headline && <PeerCard peer={data.peer_headline} />}

      {data.company && <CompanyBar data={data} />}

      {data.message && data.mode !== "INSUFFICIENT_DATA" && (
        <p className="rounded-md border-l-4 border-navy bg-panel/60 px-4 py-3 text-sm text-ink">
          {data.message}
        </p>
      )}

      {data.mode === "REJECTED" && <Notice title="Please enter a company website" body={data.message} />}
      {data.mode === "EXCLUDED" && data.content && (
        <Notice title={data.content.headline} body={data.content.body} />
      )}
      {data.mode === "INSUFFICIENT_DATA" && <Insufficient data={data} />}

      {hasScores && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {data.india_market && <ScoreCard s={data.india_market} accent="orange" />}
          {data.technology_hub && <ScoreCard s={data.technology_hub} accent="green" />}
          {data.indicative_scale && <ScaleCard scale={data.indicative_scale} />}
        </div>
      )}

      {full && data.own_evidence && data.own_evidence.length > 0 && (
        <section>
          <h2 className="border-b border-line pb-2 text-xs font-bold uppercase tracking-[0.18em] text-navy">
            What we found when we looked at your company specifically
          </h2>
          <div className="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-3">
            {data.own_evidence.map((p) => (
              <EvidenceCard key={p.title} p={p} />
            ))}
          </div>
        </section>
      )}

      {(full || data.lead_capture) && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.25fr_1fr]">
          {full && data.withheld ? <Withheld items={data.withheld} /> : <div />}
          {data.lead_capture && <Cta data={data} />}
        </div>
      )}

      {data.disclaimer && (
        <footer className="border-t border-line pt-4 text-xs leading-5 text-mute">
          {data.disclaimer}
        </footer>
      )}
    </>
  );
}

function PeerCard({ peer }: { peer: PeerHeadline }) {
  return (
    <section className="flex flex-col gap-4 rounded-md border border-line border-t-4 border-t-orange bg-white px-6 py-5 sm:flex-row sm:items-center sm:gap-8">
      <div className="whitespace-nowrap text-5xl font-extrabold text-orange sm:text-6xl">
        {peer.with_centre} of {peer.total}
      </div>
      <div>
        <p className="text-lg font-bold text-ink">
          of the companies we identify as your closest peers already run a capability centre in
          India.
        </p>
        <p className="mt-1 text-sm text-mute">
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
  const facts = [c.sector, c.country, c.revenue, c.headcount].filter(Boolean);
  return (
    <section className="flex flex-col gap-2 rounded-md border border-line bg-panel px-5 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <div>
        <span className="font-bold text-ink">{c.name || c.input}</span>
        {facts.map((f) => (
          <span key={f as string} className="text-mute">
            {"  ·  "}
            {f}
          </span>
        ))}
        {data.provisional_resolution && (
          <span className="ml-2 rounded bg-white px-1.5 py-0.5 text-[11px] text-mute">
            matched from website, not a registry
          </span>
        )}
      </div>
      {data.india_status && <div className="text-ink sm:max-w-[45%] sm:text-right">{data.india_status}</div>}
    </section>
  );
}

function ScoreCard({ s, accent }: { s: ScoreBlock; accent: "orange" | "green" }) {
  const color = accent === "orange" ? "text-orange" : "text-green";
  const bar = accent === "orange" ? "bg-orange" : "bg-green";
  const top = accent === "orange" ? "border-t-orange" : "border-t-green";
  return (
    <section className={`rounded-md border border-line border-t-4 ${top} bg-white p-5`}>
      <h3 className="font-bold text-ink">{s.label}</h3>
      {s.question && <p className="mt-0.5 text-xs text-mute">{s.question}</p>}
      <div className="mt-5 flex items-end justify-between">
        <p>
          <span className={`text-5xl font-extrabold ${color}`}>{s.score}</span>
          <span className="ml-1 text-sm text-mute">/ 100</span>
        </p>
        <span className={`rounded px-2 py-1 text-[11px] font-bold uppercase ${bandStyle(s.band)}`}>
          {s.band}
        </span>
      </div>
      <div className="mt-3 h-2 w-full rounded bg-line">
        <div className={`h-2 rounded ${bar}`} style={{ width: `${s.score}%` }} />
      </div>
      <dl className="mt-4 space-y-1.5 text-xs">
        {s.sub_dimensions.map((d) => (
          <div key={d.name} className="flex justify-between">
            <dt className="text-mute">{d.name}</dt>
            <dd className="font-semibold text-ink">{d.level}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-[11px] text-mute/80">Evidence coverage {s.coverage}%</p>
    </section>
  );
}

function ScaleCard({ scale }: { scale: NonNullable<Snapshot["indicative_scale"]> }) {
  return (
    <section className="rounded-md border border-line border-t-4 border-t-navy bg-panel/70 p-5">
      <h3 className="font-bold text-ink">Indicative scale, if you moved</h3>
      <p className="mt-0.5 text-xs text-mute">{scale.note}</p>
      <Kv k="First phase team" v={scale.first_phase_team} />
      <Kv k="Indicative run-rate saving" v={scale.indicative_saving} sub={scale.saving_basis} />
      <Kv k="Time to first team live" v={scale.time_to_first_team_live} />
    </section>
  );
}

function Kv({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div className="mt-4">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-mute">{k}</p>
      <p className="text-xl font-bold text-navy">{v}</p>
      {sub && <p className="text-[11px] text-mute">{sub}</p>}
    </div>
  );
}

function EvidenceCard({ p }: { p: OwnEvidence }) {
  const dot = p.tone === "red" ? "bg-red" : p.tone === "orange" ? "bg-orange" : "bg-[#2F6FD0]";
  return (
    <section className="rounded-md border border-line bg-white p-5">
      <h3 className="flex items-center gap-2 text-sm font-bold text-ink">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        {p.title}
      </h3>
      <ul className="mt-3 space-y-2 text-sm text-mute">
        {p.bullets.map((b) => (
          <li key={b} className="flex gap-2">
            <span className="text-mute/60">•</span>
            <span>
              <Rich text={b} />
            </span>
          </li>
        ))}
      </ul>
      {p.as_of && <p className="mt-3 text-[11px] text-mute/70">Source dated {p.as_of}</p>}
    </section>
  );
}

function Withheld({ items }: { items: string[] }) {
  return (
    <section className="rounded-md border border-dashed border-mute/40 bg-white p-5">
      <h3 className="font-bold text-ink">What this snapshot deliberately does not show you</h3>
      <p className="mt-0.5 text-xs text-mute">
        These need judgement and verification, not automation. They are what the full business
        case contains.
      </p>
      <ul className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2.5 text-sm text-ink sm:grid-cols-2">
        {items.map((w) => (
          <li key={w} className="flex gap-2">
            <span className="text-mute">+</span>
            {w}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Cta({ data }: { data: Snapshot }) {
  const lc = data.lead_capture!;
  const [sent, setSent] = useState(false);
  const button: Record<string, string> = {
    business_case: "Request my business case",
    sector_briefing: "Send me the sector briefing",
    route_to_partner: "Speak to a partner",
    complete_the_picture: "Complete my assessment",
  };
  return (
    <section className="rounded-md bg-navy p-6 text-white">
      <h3 className="text-lg font-bold">{lc.title ?? "Get the full business case in two weeks"}</h3>
      {lc.offer && <p className="mt-2 text-sm text-white/85">{lc.offer}</p>}
      {lc.sla && <p className="mt-1 text-sm text-white/85">We respond within {lc.sla}.</p>}
      {sent ? (
        <p className="mt-5 rounded bg-white/10 px-4 py-3 text-sm">
          Thank you. (Demo: wire this to Airopa's CRM before launch.)
        </p>
      ) : (
        <form
          className="mt-5 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            setSent(true);
          }}
        >
          <input
            required
            type="email"
            placeholder="Work email"
            className="w-full rounded-md border border-white/30 bg-white/10 px-4 py-3 text-white outline-none placeholder:text-white/60 focus:border-white"
          />
          <button
            type="submit"
            className="w-full rounded-md bg-white px-4 py-3 font-semibold text-navy hover:bg-panel"
          >
            {button[lc.type] ?? "Request"}
          </button>
        </form>
      )}
    </section>
  );
}

function Insufficient({ data }: { data: Snapshot }) {
  return (
    <section className="rounded-md border border-line bg-white p-6">
      <h2 className="text-xl font-bold text-ink">{data.message}</h2>
      <p className="mt-2 text-sm text-mute">
        We publish only what we can verify. We found {data.verified_count} verified data
        points, which is not enough for an honest snapshot.
      </p>
      {data.ask && (
        <>
          <p className="mt-5 text-xs font-bold uppercase tracking-widest text-navy">
            Tell us these and we complete the picture
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-ink">
            {data.ask.map((a) => (
              <li key={a} className="flex gap-2">
                <span className="text-mute">+</span>
                {a}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Notice({ title, body }: { title?: string; body?: string }) {
  return (
    <section className="rounded-md border border-line bg-white p-6">
      <h2 className="text-xl font-bold text-ink">{title}</h2>
      {body && <p className="mt-2 text-mute">{body}</p>}
    </section>
  );
}
