/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: "#0b1326",
        "surface-container": "#171f33",
        "surface-container-high": "#222a3d",
        "surface-container-lowest": "#060e20",
        "surface-variant": "#2d3449",
        "on-surface": "#dae2fd",
        "on-surface-variant": "#c2c6d6",
        primary: "#adc6ff",
        "primary-container": "#4d8eff",
        "on-primary-container": "#00285d",
        secondary: "#44e2cd",
        error: "#ffb4ab",
        "outline-variant": "#424754",
        background: "#0b1326",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        bubble: "24px",
        card: "12px",
      },
      spacing: {
        gutter: "24px",
      },
      animation: {
        "slide-down-header": "slideDownHeader 0.5s ease-out forwards",
        "slide-down-banner": "slideDownBanner 0.3s ease-out forwards",
        "fade-up-msg": "fadeUpMsg 0.25s ease-out forwards",
        "fade-up-page": "fadeUpPage 0.3s ease-out forwards",
        shake: "shake 0.2s ease-in-out",
      },
      keyframes: {
        slideDownHeader: {
          from: { transform: "translateY(-100%)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        slideDownBanner: {
          from: { transform: "translateY(-20px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        fadeUpMsg: {
          from: { transform: "translateY(12px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        fadeUpPage: {
          from: { transform: "translateY(10px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        shake: {
          "0%, 100%": { transform: "translateX(0)" },
          "25%": { transform: "translateX(-4px)" },
          "75%": { transform: "translateX(4px)" },
        },
      },
    },
  },
  plugins: [],
};
