import { useState } from "react";
import { assessCompany } from "../api";
import type { InternalBrief, InternalScore } from "../types";

const bandColor = (band: string) =>
  band === "Very strong" ? "#0D7680" : band === "Strong" ? "#0F5156" :
  band === "Moderate" ? "#B86B00" : "#990F3D";

export function InternalView() {
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [brief, setBrief] = useState<InternalBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setBrief(await assessCompany(url.trim(), token || undefined));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <p className="text-xs font-semibold uppercase tracking-[0.25em] text-ink">
        Airopa · Internal assessment
      </p>
      <h1 className="mt-2 font-serif text-3xl font-bold text-ink">Pipeline view</h1>
      <p className="mt-1 text-sm text-mute">
        Full assessment including GCC Fit. Internal only — never published.
      </p>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="company.com"
          className="flex-1 rounded-md border border-line bg-white px-4 py-3 text-ink outline-none focus:border-ink"
        />
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="internal token (if set)"
          className="rounded-md border border-line bg-white px-4 py-3 text-ink outline-none focus:border-ink"
        />
        <button
          onClick={run}
          disabled={loading || !url.trim()}
          className="rounded-md bg-ink px-6 py-3 font-semibold text-paper disabled:opacity-60"
        >
          {loading ? "Assessing…" : "Assess"}
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-claret">{error}</p>}

      {brief && (
        <div className="mt-8 space-y-6">
          <section className="rounded-lg border border-line bg-white p-5">
            <h2 className="font-serif text-xl font-bold text-ink">
              {(brief.entity.resolved_name as string) || "Unresolved entity"}
            </h2>
            <p className="text-sm text-mute">
              {[brief.entity.sector, brief.entity.country, brief.entity.registry_id]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {brief.gate && (
              <div className="mt-3 inline-flex items-center gap-2 rounded bg-paper px-3 py-1 text-sm">
                <span className="font-semibold text-ink">Gate:</span>
                <span className="font-semibold text-claret">{brief.gate.verdict}</span>
                <span className="text-mute">— {brief.gate.reason}</span>
              </div>
            )}
          </section>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {(["gcc_fit", "india_market", "technology_hub"] as const).map((k) => {
              const s = brief.scores[k];
              return s ? <ScoreCard key={k} s={s} /> : (
                <div key={k} className="rounded-lg border border-dashed border-line p-4 text-sm text-mute">
                  {k} not computed (record stopped earlier).
                </div>
              );
            })}
          </div>

          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Panel title="Narrative mode">
              <span className="font-semibold text-ink">{brief.narrative_mode ?? "—"}</span>
            </Panel>
            <Panel title="Flags">
              {brief.flags.length ? brief.flags.join(", ") : "none"}
            </Panel>
          </section>

          {brief.exclusions.length > 0 && (
            <Panel title="Exclusions & flags">
              <ul className="space-y-1 text-sm">
                {brief.exclusions.map((e) => (
                  <li key={e.code}>
                    <span className="font-semibold text-claret">{e.code}</span>{" "}
                    <span className="text-mute">({e.disposition})</span> — {e.rationale}
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {brief.recommended_model && (
            <Panel title="Recommended engagement model">
              <p className="font-semibold text-ink">{brief.recommended_model.model}</p>
              <p className="text-sm text-mute">{brief.recommended_model.rationale}</p>
            </Panel>
          )}

          <Panel title={`Sources (${brief.source_urls.length})`}>
            <ul className="max-h-40 overflow-auto text-xs text-oxford">
              {brief.source_urls.map((u) => (
                <li key={u} className="truncate">{u}</li>
              ))}
            </ul>
          </Panel>
        </div>
      )}
    </div>
  );
}

function ScoreCard({ s }: { s: InternalScore }) {
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-ink">{s.label}</h3>
        <span className="font-serif text-3xl font-bold" style={{ color: bandColor(s.band) }}>
          {s.score}
        </span>
      </div>
      <p className="text-xs text-mute">
        {s.band} · coverage {s.coverage_pct}% · {s.resolved_signals}/{s.applicable_signals} signals
      </p>
      <div className="mt-3 space-y-2">
        {s.dimensions.map((d) => (
          <div key={d.name}>
            <div className="flex justify-between text-xs text-ink">
              <span>{d.name}</span>
              <span className="text-mute">
                {d.points}/{d.max}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded bg-line">
              <div
                className="h-1.5 rounded"
                style={{
                  width: `${(d.points / d.max) * 100}%`,
                  background: bandColor(s.band),
                }}
              />
            </div>
            <p className="mt-0.5 text-[11px] text-mute">{d.basis}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-mute">{title}</p>
      <div className="mt-2 text-ink">{children}</div>
    </section>
  );
}
