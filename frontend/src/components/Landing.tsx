import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { getExamples } from "../api";

export function Landing({
  onSubmit,
  loading,
  error,
}: {
  onSubmit: (url: string) => void;
  loading: boolean;
  error: string | null;
}) {
  const [url, setUrl] = useState("");
  const [examples, setExamples] = useState<string[]>([]);

  useEffect(() => {
    getExamples().then(setExamples);
  }, []);

  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center px-6 pt-16 text-center sm:pt-24">
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-xs font-semibold uppercase tracking-[0.25em] text-claret"
      >
        Airopa · India Capability Centres
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="mt-5 font-serif text-4xl font-bold leading-[1.1] text-ink sm:text-6xl"
      >
        See your India opportunity in about 90 seconds.
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        className="mt-5 max-w-xl text-lg text-mute"
      >
        Enter your company website. We assess, from public sources alone, whether
        India is a market for what you sell and whether it can supply the talent you
        need — then show you how your competitors already have.
      </motion.p>

      <motion.form
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18 }}
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) onSubmit(url.trim());
        }}
        className="mt-10 flex w-full max-w-xl flex-col gap-3 sm:flex-row"
      >
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="yourcompany.com"
          className="flex-1 rounded-md border border-line bg-white px-5 py-4 text-lg text-ink outline-none focus:border-claret"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-claret px-7 py-4 text-lg font-semibold text-paper transition hover:bg-[#7a0c30] disabled:opacity-60"
        >
          {loading ? "Scoring…" : "Score my company"}
        </button>
      </motion.form>

      {error && <p className="mt-4 text-sm text-claret">{error}</p>}

      {examples.length > 0 && (
        <div className="mt-8">
          <p className="text-xs uppercase tracking-widest text-mute">
            Or try an illustrative example
          </p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {examples.map((d) => (
              <button
                key={d}
                onClick={() => onSubmit(d)}
                disabled={loading}
                className="rounded-full border border-line bg-white px-3 py-1.5 text-sm text-ink transition hover:border-claret hover:text-claret"
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && <Scanning />}

      <p className="mt-16 max-w-lg text-xs text-mute/80">
        Everything shown comes from public sources and names no individuals. Unverified
        figures are omitted, never estimated.
      </p>
    </div>
  );
}

function Scanning() {
  const steps = [
    "Resolving the entity",
    "Screening the India gate",
    "Gathering public signals",
    "Comparing against peers",
    "Composing your snapshot",
  ];
  return (
    <div className="mt-12 w-full max-w-md">
      {steps.map((s, i) => (
        <motion.div
          key={s}
          initial={{ opacity: 0.3 }}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.6, delay: i * 0.3, repeat: Infinity }}
          className="flex items-center gap-3 py-1.5 text-left text-sm text-ink"
        >
          <span className="h-2 w-2 rounded-full bg-claret" />
          {s}
        </motion.div>
      ))}
    </div>
  );
}
