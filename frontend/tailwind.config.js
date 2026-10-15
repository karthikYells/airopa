/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FFF1E5",
        ink: "#1A1817",
        claret: "#990F3D",
        teal: "#0F5156",
        oxford: "#0D7680",
        mute: "#66605C",
        line: "#E6D9CE",
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
