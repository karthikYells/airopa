/** @type {import('tailwindcss').Config} */
// Brand tokens from accessindia.nl (the GCC Business Case engine), so this
// engine reads as part of the same site. Token names kept from the mockup build.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#18191E",       // site band: headers, CTA, GCC Fit
        orange: "#E8791C",     // site accent: peer headline, India Market
        "orange-ink": "#B85A0B",
        "orange-soft": "#FBEBDC",
        green: "#1E9E6A",      // Technology Hub
        red: "#C0392B",
        amber: "#B7791F",
        ink: "#1A1B20",
        mute: "#5C5E66",
        line: "#E2E1DD",
        canvas: "#F6F6F4",
        panel: "#F1F0EC",
        "band-fg": "#F3F2EF",
        "band-muted": "#A3A5AD",
        "band-line": "#2E3038",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', '"Avenir Next"', '"Segoe UI"', "system-ui", "sans-serif"],
        sans: ['"IBM Plex Sans"', '"Segoe UI"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Menlo", "monospace"],
      },
      borderRadius: { panel: "14px" },
    },
  },
  plugins: [],
};
