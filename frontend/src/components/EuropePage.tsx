import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { scoreEuropeStream } from "../api";
import type { EuropeProgress, HubCard, Snapshot } from "../types";
import {
  CompanyBar, EvidenceCard, Notice, PeerCard, ReasonedCard, ReportForm, SectionLabel, SummaryPanel, Withheld,
} from "./PublicPage";
import { DomainInput, Scanning, SiteFooter, SiteHeader, companyFromUrl, setCompanyInUrl } from "./ui";

/** The Europe Market Assessment: Engine 03 for Indian companies (spec v1.1). */
export function EuropePage() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState("");
  const [progress, setProgress] = useState<EuropeProgress | null>(null);

  useEffect(() => {
    const shared = companyFromUrl();
    if (shared) run(shared);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (url: string, products: string[] = []) => {
    setDomain(url);
    setCompanyInUrl(url);
    setLoading(true);
    setError(null);
    setData(null);
    setProgress(null);
    try {
      setData(await scoreEuropeStream(url, products, setProgress));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setProgress(null);
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
          hint="We read your public website and annual report, European trade data and professional profiles. Nothing is asked of you. A first check takes one to two minutes."
        />
        {error && <p className="text-sm text-red">{error}</p>}
        {loading && (progress ? <ProgressView p={progress} /> : <Scanning />)}
        {data && <EuropeBody data={data} onProducts={(products) => run(domain, products)} />}
      </main>
      <SiteFooter />
    </>
  );
}

function EuropeBody({ data, onProducts }: { data: Snapshot; onProducts: (products: string[]) => void }) {
  if (data.mode === "REJECTED") return <Notice title="Please enter a company website" body={data.message} />;
  const unread = data.mode === "NO_OFFERING" || data.mode === "NOT_READ";
  const card = (s: HubCard, accent: "orange" | "green", key: "insight" | "reason") => (
    <ReasonedCard accent={accent} label={s.label} question={s.question} score={s.score} band={s.band}
      why={s.why} basis={s.basis}
      dims={s.dimensions.map((d: any) => ({ name: d.name, level: d.level, reason: d[key] ?? d.reason ?? d.insight }))} />
  );
  return (
    <>
      {data.peer_headline && <PeerCard peer={data.peer_headline} />}
      {data.company && <CompanyBar data={data} />}
      {data.summary && <SummaryPanel s={data.summary} />}
      {data.message && (
        <p className="rounded-panel border-l-4 border-orange bg-orange-soft px-5 py-3 text-[15px] text-ink">{data.message}</p>
      )}
      {unread && <ProductsForm prominent initial={[]} onSubmit={onProducts} />}

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
          <div className={`grid grid-cols-1 gap-5 ${data.own_evidence.length === 4 ? "lg:grid-cols-2" : "lg:grid-cols-3"}`}>
            {data.own_evidence.map((p) => <EvidenceCard key={p.title} p={p} />)}
          </div>
          {!unread && <ProductsForm initial={data.products_named ?? []} onSubmit={onProducts} />}
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

/** What is known while the check runs: the company first, then its products
 *  and Europe's demand for them, then the rest. */
function ProgressView({ p }: { p: EuropeProgress }) {
  const c = p.company;
  const step = (done: boolean, active: boolean, label: string, body?: ReactNode) => (
    <li className="grid grid-cols-[18px_1fr] gap-3">
      <span className={`mt-[6px] h-2.5 w-2.5 rounded-full ${done ? "bg-green" : active ? "animate-pulse bg-orange" : "bg-line"}`} />
      <div>
        <p className={`text-[15px] ${done || active ? "text-ink" : "text-mute"}`}>{label}</p>
        {body}
      </div>
    </li>
  );
  const hasProducts = p.stage === "products";
  const told = p.products_source === "visitor";
  return (
    <section className="rounded-panel border border-line bg-white p-6" aria-live="polite">
      <ol className="space-y-4">
        {step(true, false, "Read your website and company record",
          c?.name ? (
            <p className="mt-1 text-[14px] text-mute">
              <b className="text-ink">{c.name}</b>
              {[c.location, c.headcount].filter(Boolean).map((x) => ` · ${x}`).join("")}
            </p>
          ) : undefined)}
        {step(hasProducts, !hasProducts,
          hasProducts
            ? (told ? "Matched the products you told us to European trade data" : "Matched your products to European trade data")
            : "Matching your products to European trade data",
          hasProducts ? (p.products?.length ? (
            <ul className="mt-2 space-y-1.5">
              {p.products.map((x) => (
                <li key={x.name} className="text-[14px] text-mute">
                  <b className="text-ink">{x.name}</b>{x.demand ? `: Europe imports ${x.demand}` : ""}
                </li>
              ))}
            </ul>
          ) : <p className="mt-1 text-[14px] text-mute">We could not tell from your website what you sell.</p>) : undefined)}
        {step(false, hasProducts, "Checking your readiness, the best countries and who already sells there",
          <p className="mt-1 text-[13px] text-mute">This part takes up to a minute more.</p>)}
      </ol>
    </section>
  );
}

/** The visitor's own products: to complete a check when we could not read
 *  the site, or to correct our match. Up to three, in their words. */
function ProductsForm({ initial, onSubmit, prominent = false }: {
  initial: string[]; onSubmit: (products: string[]) => void; prominent?: boolean;
}) {
  const [items, setItems] = useState<string[]>([initial[0] ?? "", initial[1] ?? "", initial[2] ?? ""]);
  const [open, setOpen] = useState(prominent);
  const filled = items.map((x) => x.trim()).filter(Boolean);
  const examples = ["e.g. Cotton bath towels", "e.g. Kitchen linen", "e.g. Bed sheets"];
  const form = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (filled.length) onSubmit(filled);
      }}
      className="space-y-3"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {items.map((v, i) => (
          <input
            key={i}
            id={`product-${i}`}
            value={v}
            maxLength={80}
            aria-label={`Product or service ${i + 1}`}
            placeholder={examples[i]}
            onChange={(e) => setItems(items.map((x, j) => (j === i ? e.target.value : x)))}
            className="rounded-md border border-line bg-white px-3 py-2.5 text-[15px] text-ink outline-none focus:border-orange"
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!filled.length}
          className="rounded-md bg-orange px-5 py-2.5 text-[15px] font-semibold text-white disabled:opacity-40">
          Assess these products
        </button>
        <span className="text-[13px] text-mute">We match them to official EU trade codes. Takes about a minute.</span>
      </div>
    </form>
  );
  if (prominent) {
    return (
      <section className="rounded-panel border border-line border-t-4 border-t-orange bg-white p-6">
        <h3 className="text-[18px] font-bold text-ink">Tell us what you sell</h3>
        <p className="mb-4 mt-1 text-[14.5px] text-mute">Name your two or three main products or services, in your own words.</p>
        {form}
      </section>
    );
  }
  return (
    <div className="rounded-panel border border-dashed border-line px-5 py-4">
      {open ? form : (
        <button type="button" onClick={() => setOpen(true)}
          className="text-[14.5px] font-semibold text-orange underline-offset-4 hover:underline">
          Not your products? Correct them and we will assess again
        </button>
      )}
    </div>
  );
}
