import { animate, motion, useInView } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const bandColor = (band: string) => {
  switch (band) {
    case "Very strong":
      return "#0D7680";
    case "Strong":
      return "#0F5156";
    case "Moderate":
      return "#B86B00";
    default:
      return "#990F3D";
  }
};

export function ScoreGauge({
  label,
  score,
  band,
  coverage,
  subDimensions,
  delay = 0,
}: {
  label: string;
  score: number;
  band: string;
  coverage: number;
  subDimensions: string[];
  delay?: number;
}) {
  const r = 70;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = bandColor(band);
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });

  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, score, {
      duration: 1.1,
      delay,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [inView, score, delay]);

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay }}
      className="flex flex-col items-center text-center"
    >
      <div className="relative" style={{ width: 180, height: 180 }}>
        <svg width="180" height="180" viewBox="0 0 180 180">
          <circle cx="90" cy="90" r={r} fill="none" stroke="#E6D9CE" strokeWidth="12" />
          <motion.circle
            cx="90"
            cy="90"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            transform="rotate(-90 90 90)"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            whileInView={{ strokeDashoffset: circ * (1 - pct) }}
            viewport={{ once: true }}
            transition={{ duration: 1.1, delay, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-serif text-5xl font-bold text-ink">{display}</span>
          <span className="text-xs uppercase tracking-wider text-mute">out of 100</span>
        </div>
      </div>
      <div
        className="mt-3 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white"
        style={{ background: color }}
      >
        {band}
      </div>
      <h3 className="mt-3 font-serif text-lg font-bold text-ink">{label}</h3>
      <ul className="mt-2 space-y-1">
        {subDimensions.map((s) => (
          <li key={s} className="text-sm text-mute">
            {s}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] uppercase tracking-wider text-mute/80">
        Coverage {coverage}%
      </p>
    </motion.div>
  );
}
