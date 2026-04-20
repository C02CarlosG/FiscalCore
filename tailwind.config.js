/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
    "./AuditoriaFiscalDashboard.jsx",
  ],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground:  "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        border: "hsl(var(--border))",
        input:  "hsl(var(--input))",
        ring:   "hsl(var(--ring))",
        risk: {
          critical: "#F87171",
          high:     "#FB923C",
          medium:   "#FBBF24",
          low:      "#34D399",
        },
      },
      fontFamily: {
        sans:    ["'Outfit'", "sans-serif"],
        display: ["'Bricolage Grotesque'", "sans-serif"],
        brand:   ["'Exo 2'", "sans-serif"],
        serif:   ["'Cormorant Garamond'", "Georgia", "serif"],
        dmsans:  ["'DM Sans'", "sans-serif"],
        mono:    ["'JetBrains Mono'", "monospace"],
      },
      boxShadow: {
        "cyan-glow": "0 0 24px rgba(6,182,212,0.18), 0 0 48px rgba(6,182,212,0.06)",
        "card-dark": "0 1px 3px rgba(0,0,0,0.5)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "fade-in":    { from: { opacity: 0, transform: "translateY(8px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        "blink":      { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.2 } },
        "pulse-cyan": { "0%,100%": { boxShadow: "0 0 0 0 rgba(6,182,212,0)" }, "50%": { boxShadow: "0 0 12px 2px rgba(6,182,212,0.3)" } },
      },
      animation: {
        "fade-in":    "fade-in 0.4s ease both",
        "blink":      "blink 1.4s infinite",
        "pulse-cyan": "pulse-cyan 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
