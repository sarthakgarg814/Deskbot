/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Peekabot LED palette (docs §I) reused for status accents
        led: {
          idle: "#3b82f6",
          working: "#22c55e",
          thinking: "#a855f7",
          reminder: "#eab308",
          error: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};
