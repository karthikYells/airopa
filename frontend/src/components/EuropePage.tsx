import { useEffect, useState } from "react";
import { scoreEurope } from "../api";
import type { HubCard, Snapshot } from "../types";
import {
  CompanyBar, EvidenceCard, Notice, ReasonedCard, ReportForm, SectionLabel, SummaryPanel, Withheld,
} from "./PublicPage";
import { DomainInput, Scanning, SiteFooter, SiteHeader, companyFromUrl, setCompanyInUrl } from "./ui";

/** The Europe Market Assessment: Engine 03 for Indian companies (spec v1.1). */
export function EuropePage() {
  const [data, setData] = useState<Snapshot | null>(null);
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
    setData(null);
    try {
      setData(await scoreEurope(url));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <SiteHeader
        crumb="Europe Market Assessment"
        title="Is Europe a market for what you sell,"
        accent="and are you ready to win it?"
        intro="For Indian companies. Enter your website and see how Europe's demand, tariffs and buyers line up with what you sell, how ready you are to win European customers, and where to start. Free, no login. Get the report as a PDF in your inbox."
      />
      <main className="mx-auto max-w-[1180px] space-y-6 px-4 pt-10 sm:px-10">
        <DomainInput
          initial={domain}
          button="Check my company"
          loading={loading}
          onSubmit={run}
          placeholder="yourcompany.in"
          hint="We read your public website and annual report, European trade data and professional profiles. Nothing is asked of you. A check takes about a minute."
        />
        {error && <p className="text-sm text-red">{error}</p>}
        {loading && <Scanning />}
        {data && <EuropeBody data={data} />}
      </main>
      <SiteFooter />
    </>
  );
}

function EuropeBody({ data }: { data: Snapshot }) {
  if (data.mode === "REJECTED") return <Notice title="Please enter a company website" body={data.message} />;
  const card = (s: HubCard, accent: "orange" | "green", key: "insight" | "reason") => (
    <ReasonedCard accent={accent} label={s.label} question={s.question} score={s.score} band={s.band}
      why={s.why} basis={s.basis}
      dims={s.dimensions.map((d: any) => ({ name: d.name, level: d.level, reason: d[key] ?? d.reason ?? d.insight }))} />
  );
  return (
    <>
      {data.company && <CompanyBar data={data} />}
      {data.summary && <SummaryPanel s={data.summary} />}
      {data.message && (
        <p className="rounded-panel border-l-4 border-orange bg-orange-soft px-5 py-3 text-[15px] text-ink">{data.message}</p>
      )}

      {(data.market || data.readiness) && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {data.market && card(data.market as unknown as HubCard, "orange", "insight")}
          {data.readiness && card(data.readiness, "green", "reason")}
        </div>
      )}

      {(data.countries?.length || data.time_to_first_order) && <WhereToStart data={data} />}

      {data.own_evidence && data.own_evidence.length > 0 && (
        <section className="space-y-4">
          <SectionLabel>What we found when we looked at your company specifically</SectionLabel>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {data.own_evidence.map((p) => <EvidenceCard key={p.title} p={p} />)}
          </div>
        </section>
      )}

      {data.run_id && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.1fr]">
          <div className="space-y-5">
            {data.lead_capture?.title && (
              <section className="rounded-panel bg-navy p-6 text-band-fg">
                <h3 className="font-display text-[22px] font-extrabold">{data.lead_capture.title}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-band-muted">{data.lead_capture.offer}</p>
              </section>
            )}
            {data.withheld && <Withheld items={data.withheld} />}
          </div>
          <ReportForm data={data} engine="europe" />
        </div>
      )}

      {data.disclaimer && (
        <p className="border-t border-line pt-4 text-[13px] leading-5 text-mute">{data.disclaimer}</p>
      )}
    </>
  );
}

/** Top 3 countries and the indicative time to a first European order, in one strip. */
function WhereToStart({ data }: { data: Snapshot }) {
  const t = data.time_to_first_order;
  return (
    <section className="grid grid-cols-1 gap-5 rounded-panel border border-line border-t-4 border-t-navy bg-[#F3F5F9] px-6 py-5 lg:grid-cols-[1.6fr_1fr]">
      <div>
        <h3 className="text-[17px] font-bold text-ink">Where to start in Europe</h3>
        <ol className="mt-3 space-y-2.5">
          {(data.countries ?? []).map((c, i) => (
            <li key={c.code} className="grid grid-cols-[26px_1fr] gap-2">
              <span className="font-display text-[20px] font-extrabold leading-6 text-orange">{i + 1}</span>
              <span className="text-[14.5px] text-mute"><b className="text-ink">{c.name}</b>: {c.why}</span>
            </li>
          ))}
          {data.uk_note && (
            <li className="grid grid-cols-[26px_1fr] gap-2">
              <span className="font-display text-[20px] font-extrabold leading-6 text-orange">+</span>
              <span className="text-[14.5px] text-mute">{data.uk_note}</span>
            </li>
          )}
        </ol>
      </div>
      {t && (
        <div className="border-t border-line pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute">Indicative time to first European order</p>
          <p className="mt-1 font-display text-[28px] font-bold leading-tight text-navy">{t.range}</p>
          <p className="mt-1 text-[13px] text-mute">Because {t.basis}.</p>
          <p className="mt-2 text-[12px] text-mute">{t.note}</p>
        </div>
      )}
    </section>
  );
}
