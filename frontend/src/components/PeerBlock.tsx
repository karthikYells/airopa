import { motion } from "framer-motion";
import type { PeerHeadline } from "../types";

export function PeerBlock({ peer }: { peer: PeerHeadline }) {
  const total = peer.total ?? 0;
  const withCentre = peer.with_centre ?? 0;
  const dots = Array.from({ length: total });

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className="border-t-2 border-ink bg-white/40 px-6 py-8 sm:px-10"
    >
      <p className="text-xs font-semibold uppercase tracking-widest text-claret">
        Your competitors
      </p>
      {total ? (
        <>
          <p className="mt-3 font-serif text-3xl leading-tight text-ink sm:text-4xl">
            <span className="font-bold text-claret">{withCentre}</span> of {total}{" "}
            comparable companies already run a capability centre in India.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {dots.map((_, i) => (
              <motion.span
                key={i}
                initial={{ scale: 0, opacity: 0 }}
                whileInView={{ scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 + i * 0.06, type: "spring", stiffness: 300 }}
                className="h-6 w-6 rounded-full"
                style={{ background: i < withCentre ? "#990F3D" : "#E6D9CE" }}
                title={i < withCentre ? "Runs an India centre" : "No centre"}
              />
            ))}
          </div>
        </>
      ) : (
        <p className="mt-3 font-serif text-3xl text-ink">
          {peer.penetration_pct}% of your peer set already run a capability centre in
          India.
        </p>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
        {peer.recent_24m != null && (
          <Fact k="Opened in the last 24 months" v={`${peer.recent_24m}`} />
        )}
        {peer.aggregate_india_headcount != null && (
          <Fact
            k="Combined India headcount"
            v={peer.aggregate_india_headcount.toLocaleString()}
          />
        )}
        {peer.cohort_definition && <Fact k="Cohort" v={peer.cohort_definition} />}
      </div>
      <p className="mt-4 text-xs italic text-mute">
        The identity of these companies is part of the full business case.
      </p>
    </motion.section>
  );
}

function Fact({ k, v }: { k: string; v: string }) {
  return (
    <div className="border-l-2 border-line pl-3">
      <div className="font-serif text-xl font-bold text-ink">{v}</div>
      <div className="text-xs uppercase tracking-wide text-mute">{k}</div>
    </div>
  );
}
