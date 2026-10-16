import { useEffect, useState, type ReactNode } from "react";
import { assessCompany } from "../api";
import type { InternalBrief, InternalScore } from "../types";
import { DomainInput, Scanning, TopBar, bandStyle, companyFromUrl, setCompanyInUrl } from "./ui";

/** The internal assessment, laid out as the Section 10.2 mockup (screen 1),
 *  followed by the evidence panels the engine can support today. */
export function InternalView() {
  const [brief, setBrief] = useState<InternalBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState("");

  useEffect(() => {
    const shared = companyFromUrl();
    if (shared) run(shared);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (url: string) => {
    setDomain(url);
    setCompanyInUrl(url);
    setLoading(true);
    setError(null);
    setBrief(null);
    try {
      setBrief(await assessCompany(url));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const stage = brief?.pipeline.reached_tier3
    ? "Tier 3 full assessment"
    : brief?.pipeline.stopped_at
      ? `Stopped at ${brief.pipeline.stopped_at}`
      : "";

  return (
    <div className="mx-auto max-w-7xl bg-white shadow-sm">
      <TopBar
        title="GCC Prospect Assessment Engine"
        right={
          brief ? (
            <>
              <div>{brief.run_at}</div>
              <div>
                Config {brief.config_version} | {stage} | {brief.source_urls.length} sources
              </div>
            </>
          ) : (
            <div>Internal only. Never published.</div>
          )
        }
      />
      <main className="space-y-6 px-5 py-6 sm:px-9">
        <DomainInput initial={domain} button="Assess" loading={loading} onSubmit={run} placeholder="company.com" />
        {error && <p className="text-sm text-red">{error}</p>}
        {loading && <Scanning />}
        {brief && <Assessment b={brief} />}
      </main>
    </div>
  );
}

function fmtEur(v?: number | null) {
  if (typeof v !== "number") return "UNKNOWN";
  return v >= 1e9 ? `EUR ${(v / 1e9).toFixed(1)}bn` : `EUR ${Math.round(v / 1e6)}m`;
}

function Assessment({ b }: { b: InternalBrief }) {
  const e = b.entity;
  const fit = b.scores.gcc_fit;
  return (
    <>
      <p className="rounded bg-panel px-4 py-2 text-xs text-mute">
        <span className="font-semibold uppercase tracking-wide">Input</span>{" "}
        <span className="font-mono font-semibold text-ink">{b.input}</span> → Resolved to{" "}
        <strong className="text-ink">{e.resolved_name || "UNRESOLVED"}</strong>
        {e.registry_id && <> · {e.registry_id}</>}
        {e.resolution_provisional && <> · provisional, no registry match</>}
        {e.ultimate_parent && <> · parent {e.ultimate_parent}</>}
      </p>

      <section className="flex flex-col gap-4 border-b-2 border-navy pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink sm:text-3xl">{e.resolved_name || b.input}</h1>
          <p className="mt-1 text-sm text-mute">
            {[e.sector, e.jurisdiction, e.founded ? `founded ${e.founded}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-4">
          <Stat k="Revenue" v={fmtEur(e.revenue_eur)} />
          <Stat k="Headcount" v={typeof e.headcount === "number" ? e.headcount.toLocaleString() : "UNKNOWN"} />
          <Stat k="India profiles" v={typeof e.india_profiles === "number" ? e.india_profiles.toLocaleString() : "UNKNOWN"} />
          <Stat k="Coverage" v={fit ? `${fit.coverage_pct}%` : "—"} />
        </div>
      </section>

      {b.gate && <GateBanner b={b} />}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <ScoreCard n={1} audience="Internal" question="Should Airopa approach this company, and with what urgency?" s={fit} color="navy" provisional={!b.pipeline.reached_tier3} />
        <ScoreCard n={2} audience="Client facing" question="Is India a revenue market for what they sell, not only a cost location?" s={b.scores.india_market} color="orange" />
        <ScoreCard n={3} audience="Client facing" question="Can India supply the specific talent and capability they need?" s={b.scores.technology_hub} color="green" />
      </div>

      <section>
        <h2 className="text-xs font-bold uppercase tracking-[0.18em] text-navy">Dimension breakdown</h2>
        <div className="mt-3 grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Dimensions s={fit} color="navy" />
          <Dimensions s={b.scores.india_market} color="orange" />
          <Dimensions s={b.scores.technology_hub} color="green" />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="Exclusions, flags and routing">
          {b.exclusions.length === 0 && b.flags.length === 0 ? (
            <p className="text-sm text-mute">No exclusion or flag triggered.</p>
          ) : (
            <ul className="space-y-1.5 text-sm">
              {b.exclusions.map((x) => (
                <li key={x.code}>
                  <span className="font-bold text-red">{x.code}</span>{" "}
                  <span className="text-mute">({x.disposition})</span> — {x.rationale}
                </li>
              ))}
              {b.flags.filter((f) => !b.exclusions.some((x) => x.code === f)).map((f) => (
                <li key={f}><span className="font-bold text-amber">{f}</span> flag</li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-sm text-ink">
            <span className="font-semibold">Narrative mode:</span> {b.narrative_mode ?? "not set (Tier 3 not reached)"}
          </p>
          {b.recommended_model && (
            <p className="mt-2 text-sm text-ink">
              <span className="font-semibold">Recommended model:</span> {b.recommended_model.model}.{" "}
              <span className="text-mute">{b.recommended_model.rationale}</span>
            </p>
          )}
          <ul className="mt-3 space-y-1 text-xs text-mute">
            {b.pipeline.notes.map((n) => <li key={n}>· {n}</li>)}
          </ul>
        </Panel>

        {b.gate && b.gate.titles.length > 0 && <TitlesPanel titles={b.gate.titles} />}
      </div>

      <Panel title={`Sources (${b.source_urls.length})`}>
        <ul className="max-h-48 space-y-0.5 overflow-auto text-xs text-[#2F6FD0]">
          {b.source_urls.map((u) => <li key={u} className="truncate">{u}</li>)}
        </ul>
      </Panel>

      <p className="border-t border-line pt-3 text-xs text-mute">
        Not yet produced, because the data sources do not exist yet: peer table and cohort rank
        (needs the peer database, spec 6.1), dated pressure from filings and press, skill
        availability against their own vacancies, IP and vendor exposure, entry points. Panels
        appear only when their signals resolve (spec 10.1).
      </p>
    </>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-mute">{k}</p>
      <p className="text-base font-bold text-ink">{v}</p>
    </div>
  );
}

function GateBanner({ b }: { b: InternalBrief }) {
  const g = b.gate!;
  const tone =
    g.verdict === "CONFIRMED" ? "border-red bg-red/5 text-red"
      : g.verdict === "CAUTION" ? "border-amber bg-amber/5 text-amber"
        : "border-green bg-green/5 text-green";
  const c = g.title_mix?.counts ?? {};
  const mix = g.title_mix?.total
    ? `India titles sampled: ${g.title_mix.total} — ${c.TECH ?? 0} technology, ${c.NON_TECH ?? 0} non-technology, ${c.AMBIGUOUS ?? 0} ambiguous, ${c.IT_SUPPORT ?? 0} IT support.`
    : "No India job titles found.";
  return (
    <section className={`flex flex-col gap-3 rounded-md border-l-4 p-4 sm:flex-row sm:items-start ${tone}`}>
      <span className={`shrink-0 rounded px-2.5 py-1 text-xs font-bold text-white ${
        g.verdict === "CONFIRMED" ? "bg-red" : g.verdict === "CAUTION" ? "bg-amber" : "bg-green"}`}>
        GATE: {g.verdict.replace("_", " ")}
      </span>
      <div className="text-sm text-ink">
        <p><strong>{g.reason}</strong> {mix}</p>
        {g.evidence_note && <p className="mt-1 text-xs text-mute">{g.evidence_note}</p>}
      </div>
    </section>
  );
}

const colors = {
  navy: { text: "text-navy", bar: "bg-navy", top: "border-t-navy" },
  orange: { text: "text-orange", bar: "bg-orange", top: "border-t-orange" },
  green: { text: "text-green", bar: "bg-green", top: "border-t-green" },
};

function ScoreCard({ n, audience, question, s, color, provisional }: {
  n: number; audience: string; question: string; s: InternalScore | null;
  color: keyof typeof colors; provisional?: boolean;
}) {
  const c = colors[color];
  return (
    <section className={`rounded-md border border-line border-t-4 ${c.top} bg-white p-5`}>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-mute">
        Score {n} of 3 · {audience}
      </p>
      <h3 className="mt-1 font-bold text-ink">{s?.label ?? (n === 1 ? "GCC Fit" : "")}</h3>
      <p className="text-xs text-mute">{question}</p>
      {s ? (
        <>
          <div className="mt-4 flex items-end justify-between">
            <p>
              <span className={`text-5xl font-extrabold ${c.text}`}>{s.score}</span>
              <span className="ml-1 text-sm text-mute">/ 100</span>
            </p>
            <span className={`rounded px-2 py-1 text-[11px] font-bold uppercase ${bandStyle(s.band)}`}>
              {s.band}
            </span>
          </div>
          <div className="mt-3 h-2 w-full rounded bg-line">
            <div className={`h-2 rounded ${c.bar}`} style={{ width: `${s.score}%` }} />
          </div>
          <div className="mt-3 flex justify-between text-xs text-mute">
            <span>{provisional ? "Provisional (Tier 2)" : `${s.resolved_signals}/${s.applicable_signals} signals`}</span>
            <span>Coverage <strong className="text-ink">{s.coverage_pct}%</strong></span>
          </div>
        </>
      ) : (
        <p className="mt-6 text-sm text-mute">Not computed: the record stopped before scoring.</p>
      )}
    </section>
  );
}

function Dimensions({ s, color }: { s: InternalScore | null; color: keyof typeof colors }) {
  const c = colors[color];
  if (!s) return <div className="rounded-md border border-dashed border-line p-4 text-sm text-mute">Not computed.</div>;
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <p className="flex items-center gap-2 text-sm font-bold text-ink">
        <span className={`h-2.5 w-2.5 rounded-full ${c.bar}`} />
        {s.label} {s.score} / 100
      </p>
      <div className="mt-3 space-y-3">
        {s.dimensions.map((d) => (
          <div key={d.name}>
            <div className="flex justify-between text-xs text-ink">
              <span>{d.name}</span>
              <span className="font-semibold">{Math.round(d.points)} / {d.max}</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded bg-line">
              <div className={`h-1.5 rounded ${c.bar}`} style={{ width: `${(d.points / d.max) * 100}%` }} />
            </div>
            <p className="mt-0.5 text-[11px] leading-4 text-mute">{d.basis}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function TitlesPanel({ titles }: { titles: InternalBrief["gate"] extends infer G ? G extends { titles: infer T } ? T : never : never }) {
  const tone: Record<string, string> = {
    TECH: "text-red", NON_TECH: "text-green", AMBIGUOUS: "text-amber", IT_SUPPORT: "text-mute",
  };
  return (
    <Panel title={`India title evidence (${titles.length})`}>
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-white text-left text-mute">
            <tr><th className="py-1">Title</th><th>Class</th><th>Method</th></tr>
          </thead>
          <tbody>
            {titles.map((t, i) => (
              <tr key={i} className="border-t border-line">
                <td className="py-1 pr-2 text-ink">{t.raw}</td>
                <td className={`font-semibold ${tone[t.class] ?? ""}`}>{t.class.replace("_", " ")}</td>
                <td className="text-mute">{t.method}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-md border border-line bg-white p-5">
      <p className="text-xs font-bold uppercase tracking-[0.15em] text-navy">{title}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}
