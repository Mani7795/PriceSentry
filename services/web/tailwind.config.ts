import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        border: "rgb(var(--color-border) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        text: "rgb(var(--color-text) / <alpha-value>)",
        primary: "rgb(var(--color-primary) / <alpha-value>)",
        "primary-fg": "rgb(var(--color-primary-fg) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
      },
    },
  },
  plugins: [typography],
};

export default config;
