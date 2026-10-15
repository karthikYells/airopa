import { motion } from "framer-motion";
import type { Snapshot } from "../types";
import { ScoreGauge } from "./ScoreGauge";
import { PeerBlock } from "./PeerBlock";

const fade = {
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.5 },
};

export function SnapshotView({ data, onReset }: { data: Snapshot; onReset: () => void }) {
  const c = data.company;
  return (
    <div className="mx-auto max-w-3xl pb-24">
      <Header data={data} onReset={onReset} />

      {data.mode === "REJECTED" && <Notice title="Try again" body={data.message} />}

      {data.mode === "EXCLUDED" && data.content && (
        <Notice title={data.content.headline} body={data.content.body} />
      )}

      {data.mode === "INSUFFICIENT_DATA" && (
        <section className="px-6 py-8 sm:px-10">
          <p className="font-serif text-2xl text-ink">{data.message}</p>
          <p className="mt-4 text-sm font-semibold uppercase tracking-wide text-mute">
            What we could verify
          </p>
          <p className="text-sm text-mute">{data.verified_count} data points.</p>
          {data.ask && (
            <>
              <p className="mt-4 text-sm font-semibold uppercase tracking-wide text-mute">
                Tell us these and we complete the picture
              </p>
              <ul className="mt-2 list-disc pl-5 text-sm text-ink">
                {data.ask.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {(data.mode === "STANDARD" || data.mode === "EXISTING_CENTRE") && (
        <>
          {data.peer_headline && <PeerBlock peer={data.peer_headline} />}

          {data.india_status && (
            <motion.section {...fade} className="px-6 py-7 sm:px-10">
              <p className="text-xs font-semibold uppercase tracking-widest text-oxford">
                Your India status
              </p>
              <p className="mt-2 font-serif text-2xl leading-snug text-ink">
                {data.india_status}
              </p>
            </motion.section>
          )}

          {(data.india_market || data.technology_hub) && (
            <section className="border-t border-line px-6 py-10 sm:px-10">
              <div className="grid grid-cols-1 gap-10 sm:grid-cols-2">
                {data.india_market && (
                  <ScoreGauge
                    label={data.india_market.label}
                    score={data.india_market.score}
                    band={data.india_market.band}
                    coverage={data.india_market.coverage}
                    subDimensions={data.india_market.sub_dimensions}
                  />
                )}
                {data.technology_hub && (
                  <ScoreGauge
                    label={data.technology_hub.label}
                    score={data.technology_hub.score}
                    band={data.technology_hub.band}
                    coverage={data.technology_hub.coverage}
                    subDimensions={data.technology_hub.sub_dimensions}
                    delay={0.15}
                  />
                )}
              </div>
            </section>
          )}

          {data.indicative_scale && (
            <motion.section
              {...fade}
              className="border-t border-line bg-ink px-6 py-9 text-paper sm:px-10"
            >
              <p className="text-xs font-semibold uppercase tracking-widest text-paper/70">
                Indicative scale
              </p>
              <div className="mt-4 grid grid-cols-1 gap-6 sm:grid-cols-3">
                <Big k="First phase team" v={data.indicative_scale.first_phase_team} />
                <Big k="Indicative saving" v={data.indicative_scale.indicative_saving} />
                <Big
                  k="Time to first team live"
                  v={data.indicative_scale.time_to_first_team_live}
                />
              </div>
              <p className="mt-4 text-xs italic text-paper/60">
                {data.indicative_scale.note}
              </p>
            </motion.section>
          )}

          {data.own_evidence && data.own_evidence.length > 0 && (
            <section className="border-t border-line px-6 py-9 sm:px-10">
              <p className="text-xs font-semibold uppercase tracking-widest text-claret">
                Your own evidence
              </p>
              <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
                {data.own_evidence.map((p, i) => (
                  <motion.div
                    key={p.title}
                    initial={{ opacity: 0, y: 14 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                    className="border-t-2 border-ink pt-3"
                  >
                    <h4 className="font-serif text-lg font-bold text-ink">{p.title}</h4>
                    <p className="mt-1 text-sm text-mute">{p.detail}</p>
                    {p.as_of && (
                      <p className="mt-2 text-[11px] uppercase tracking-wide text-mute/70">
                        As of {p.as_of}
                      </p>
                    )}
                  </motion.div>
                ))}
              </div>
            </section>
          )}

          {data.withheld && (
            <motion.section
              {...fade}
              className="border-t border-line bg-white/50 px-6 py-9 sm:px-10"
            >
              <p className="text-xs font-semibold uppercase tracking-widest text-mute">
                What this snapshot does not show
              </p>
              <ul className="mt-4 space-y-2">
                {data.withheld.map((w) => (
                  <li key={w} className="flex items-start gap-2 text-sm text-ink">
                    <span className="mt-[2px] text-claret">▸</span>
                    {w}
                  </li>
                ))}
              </ul>
            </motion.section>
          )}
        </>
      )}

      {data.mode === "SUB_SCALE" && (
        <section className="px-6 py-8 sm:px-10">
          <p className="font-serif text-2xl text-ink">{data.message}</p>
          {data.india_market && (
            <div className="mt-8 flex justify-center">
              <ScoreGauge
                label={data.india_market.label}
                score={data.india_market.score}
                band={data.india_market.band}
                coverage={data.india_market.coverage}
                subDimensions={data.india_market.sub_dimensions}
              />
            </div>
          )}
        </section>
      )}

      {data.mode === "ENTERPRISE" && (
        <section className="px-6 py-8 sm:px-10">
          <p className="font-serif text-2xl text-ink">{data.message}</p>
          <div className="mt-8 grid grid-cols-1 gap-10 sm:grid-cols-2">
            {data.india_market && (
              <ScoreGauge {...toGauge(data.india_market)} />
            )}
            {data.technology_hub && (
              <ScoreGauge {...toGauge(data.technology_hub)} delay={0.15} />
            )}
          </div>
        </section>
      )}

      {data.lead_capture && <LeadCapture data={data} />}

      {data.disclaimer && (
        <footer className="border-t border-line px-6 py-6 text-center text-xs text-mute sm:px-10">
          {data.disclaimer}
        </footer>
      )}
    </div>
  );
}

function toGauge(s: NonNullable<Snapshot["india_market"]>) {
  return {
    label: s.label,
    score: s.score,
    band: s.band,
    coverage: s.coverage,
    subDimensions: s.sub_dimensions,
  };
}

function Header({ data, onReset }: { data: Snapshot; onReset: () => void }) {
  const c = data.company;
  return (
    <div className="px-6 pt-8 sm:px-10">
      <button
        onClick={onReset}
        className="text-xs font-semibold uppercase tracking-widest text-claret hover:underline"
      >
        ← Score another company
      </button>
      {c && (
        <div className="mt-4">
          <h1 className="font-serif text-3xl font-bold leading-tight text-ink sm:text-4xl">
            {c.name || c.input}
          </h1>
          <p className="mt-1 text-sm text-mute">
            {[c.sector, c.country].filter(Boolean).join(" · ")}
          </p>
          {data.provisional_resolution && (
            <p className="mt-2 inline-block rounded bg-white/60 px-2 py-1 text-[11px] text-mute">
              Provisional match from the public website — not a registry confirmation.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function LeadCapture({ data }: { data: Snapshot }) {
  const lc = data.lead_capture!;
  const labels: Record<string, string> = {
    business_case: "Get the full business case",
    sector_briefing: "Send me the sector briefing",
    route_to_partner: "Speak to a partner",
    complete_the_picture: "Complete my assessment",
  };
  return (
    <motion.section
      {...fade}
      className="mx-6 my-10 rounded-xl border border-claret/30 bg-claret px-6 py-8 text-paper sm:mx-10 sm:px-10"
    >
      {lc.offer && <p className="font-serif text-xl leading-snug">{lc.offer}</p>}
      {lc.sla && (
        <p className="mt-2 text-sm text-paper/80">We respond within {lc.sla}.</p>
      )}
      <form
        className="mt-5 flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          alert("Demo: work email captured. Wire this to Airopa's CRM on launch.");
        }}
      >
        <input
          required
          type="email"
          placeholder="you@yourcompany.com"
          className="flex-1 rounded-md border-0 px-4 py-3 text-ink outline-none"
        />
        <button
          type="submit"
          className="rounded-md bg-ink px-5 py-3 font-semibold text-paper transition hover:bg-black"
        >
          {labels[lc.type] ?? "Request"}
        </button>
      </form>
    </motion.section>
  );
}

function Big({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="font-serif text-2xl font-bold">{v}</div>
      <div className="mt-1 text-xs uppercase tracking-wide text-paper/70">{k}</div>
    </div>
  );
}

function Notice({ title, body }: { title?: string; body?: string }) {
  return (
    <section className="px-6 py-10 sm:px-10">
      <h2 className="font-serif text-2xl font-bold text-ink">{title}</h2>
      <p className="mt-3 text-mute">{body}</p>
    </section>
  );
}
