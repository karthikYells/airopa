/** @type {import('tailwindcss').Config} */
// Palette taken from the spec mockups (Sections 9.9 and 10.2).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#1F3864",       // header bars, CTA, indicative scale, GCC Fit
        orange: "#E8662A",     // peer headline, India Market
        green: "#1E9E6A",      // Technology Hub
        red: "#C0392B",        // IP exposure, CONFIRMED gate
        amber: "#B7791F",      // CAUTION
        ink: "#1B2430",        // body text
        mute: "#5B6575",       // secondary text
        line: "#DDE3EA",       // borders
        canvas: "#F4F6F9",     // page background
        panel: "#EEF2F7",      // light grey bands
      },
      fontFamily: {
        sans: ["Inter", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
