/** @type {import('tailwindcss').Config} */
// DIN Brand Guidelines v1.0 + Mobile Annex v1.0.
// - Exact brand HEX values from master §4.1
// - darkMode: 'class' so we can toggle and default-by-viewport
//   (mobile = dark, desktop = light, per Mobile Annex §6.1)
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        "din-red": "#C8202F",
        "din-red-soft": "#D43545",
        "din-gold": "#E8A82A",
        "din-gold-soft": "#F0BB52",
        "din-blue": "#4A6B8A",
        "din-blue-dark": "#3A5670",
        "din-navy": "#1A2332",
        "din-navy-soft": "#2A3548",
        "din-cream": "#F5EEE0",
        "din-cream-soft": "#FAF6EC",
      },
      fontFamily: {
        display: ["Oswald", "Impact", "Arial Black", "sans-serif"],
        body: ["Arial", "Helvetica", "sans-serif"],
        mono: ["Courier New", "Consolas", "monospace"],
      },
      // Two-iteration pulse used to draw the eye to Send right after a
      // dictation lands in the textarea. Brand-gold ring + light scale.
      keyframes: {
        "send-pulse": {
          "0%, 100%": {
            transform: "scale(1)",
            boxShadow: "0 0 0 0 rgba(232, 168, 42, 0)",
          },
          "50%": {
            transform: "scale(1.06)",
            boxShadow: "0 0 0 8px rgba(232, 168, 42, 0.35)",
          },
        },
      },
      animation: {
        "send-pulse": "send-pulse 0.7s ease-in-out 2",
      },
    },
  },
  plugins: [],
};
