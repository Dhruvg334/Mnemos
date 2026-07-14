/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./lib/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#ffffff",
          alt: "#f6f7f9",
          sunk: "#eef0f3",
        },
        ink: {
          DEFAULT: "#14151a",
          soft: "#53565f",
          faint: "#8b8e97",
        },
        line: {
          DEFAULT: "#e2e4e9",
          strong: "#cdd0d7",
        },
        rail: {
          DEFAULT: "#101114",
          raised: "#1a1c21",
          line: "#2b2e35",
          ink: "#eceef2",
          soft: "#9a9dab",
        },
        signal: {
          blue: "#2f6fe0",
          "blue-deep": "#1f4fb0",
          "blue-pale": "#eaf2fd",
          "blue-line": "#bdd6f7",
          amber: "#8a6d1f",
          "amber-pale": "#faf3e0",
          red: "#a23b2e",
          "red-pale": "#fbeae7",
          "red-line": "#f0c7bd",
          green: "#2f7a4f",
          "green-pale": "#e9f5ee",
        },
      },
      fontFamily: {
        ui: ["'IBM Plex Sans'", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        drawer: "-14px 0 34px -18px rgba(16,17,20,.35)",
        pop: "0 10px 30px -12px rgba(16,17,20,.18)",
      },
      keyframes: {
        "fade-in": { from: { opacity: 0 }, to: { opacity: 1 } },
        "slide-up": { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in .15s ease-out",
        "slide-up": "slide-up .18s cubic-bezier(.2,.7,.3,1)",
      },
    },
  },
  plugins: [],
};
