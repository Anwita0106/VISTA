/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Site-wide warm theme: the former navy/slate scales are remapped to honey and warm-neutral tones,
        // so every page shares the cream-and-yellow look without changing any page logic.
        navy: { 50: "#FFF7E6", 100: "#FCEBC4", 200: "#F6D98C", 300: "#F2C14E", 400: "#E9A23B", 500: "#C98524", 600: "#A86C1B", 700: "#8F5F14", 800: "#6E4A12", 900: "#493522", 950: "#2E2114" },
        slate: { 50: "#FFF8E8", 100: "#FAEFD9", 200: "#EFE2C9", 300: "#E3D2B4", 400: "#A08C70", 500: "#7A6953", 600: "#6B5A45", 700: "#574634", 800: "#493522", 900: "#3A2A1B" },
        white: "#FFFEFA",
        // VISTA cream-and-yellow theme
        vista: {
          bg: "#FFF8E8", side: "#FFF3D6", card: "#FFFEFA", yellow: "#F2C14E", accent: "#E9A23B", "accent-hover": "#DE9630",
          soft: "#FBEBC2", ink: "#493522", muted: "#887761", "muted-text": "#7A6953", link: "#8F5F14", line: "#EFE2C9", sos: "#DC2626",
        },
      },
      boxShadow: { soft: "0 1px 2px rgba(73,53,34,0.04), 0 6px 18px -8px rgba(73,53,34,0.12)" },
      fontFamily: { sans: ["Plus Jakarta Sans Variable", "Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"] },
    },
  },
  plugins: [],
};
