/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: "#0b0e14",
        surface: "#121721",
        "surface-raised": "#192231",
        "surface-border": "#222f44",
        primary: {
          DEFAULT: "#00d2ff",
          hover: "#00b4db",
          glow: "rgba(0, 210, 255, 0.25)"
        },
        trade: {
          up: "#00f298",
          upGlow: "rgba(0, 242, 152, 0.25)",
          down: "#ff3366",
          downGlow: "rgba(255, 51, 102, 0.25)",
          warning: "#ffb800",
          neutral: "#8a99ad"
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 210, 255, 0.25)',
        'glow-green': '0 0 20px rgba(0, 242, 152, 0.25)',
        'glow-red': '0 0 20px rgba(255, 51, 102, 0.25)',
      }
    },
  },
  plugins: [],
}
