import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark Theme Base
        dark: {
          bg: "#0A0A0F",
          card: "#12121A",
          elevated: "#1A1A24",
          border: "#2A2A3A",
        },
        // Accent Colors
        accent: {
          cyan: "#00D9FF",
          purple: "#8B5CF6",
          pink: "#EC4899",
          orange: "#F97316",
          green: "#10B981",
        },
        // Gradients will use these
        gradient: {
          start: "#8B5CF6",
          end: "#00D9FF",
        },
      },
      backgroundImage: {
        "gradient-card": "linear-gradient(135deg, #8B5CF6 0%, #00D9FF 100%)",
        "gradient-button": "linear-gradient(90deg, #8B5CF6 0%, #00D9FF 100%)",
        "gradient-progress": "linear-gradient(90deg, #8B5CF6 0%, #00D9FF 100%)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
        "4xl": "2rem",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
