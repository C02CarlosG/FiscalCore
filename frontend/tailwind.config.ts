import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
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
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        severity: {
          critico: {
            DEFAULT: "var(--severity-critico)",
            soft: "var(--severity-critico-soft)",
          },
          alto: {
            DEFAULT: "var(--severity-alto)",
            soft: "var(--severity-alto-soft)",
          },
          medio: {
            DEFAULT: "var(--severity-medio)",
            soft: "var(--severity-medio-soft)",
          },
          bajo: {
            DEFAULT: "var(--severity-bajo)",
            soft: "var(--severity-bajo-soft)",
          },
        },
        status: {
          ok: { DEFAULT: "var(--status-ok)", soft: "var(--status-ok-soft)" },
          pendiente: {
            DEFAULT: "var(--status-pendiente)",
            soft: "var(--status-pendiente-soft)",
          },
          error: {
            DEFAULT: "var(--status-error)",
            soft: "var(--status-error-soft)",
          },
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-public-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-sora)", "var(--font-public-sans)", "system-ui"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
