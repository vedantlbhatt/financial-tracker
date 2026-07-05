/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'system-ui', 'sans-serif'],
      },
      colors: {
        // ── Light neumorphic palette ──────────────────────────────────────
        'neu-bg': '#e0e5ec',
        'neu-surface': '#e8ecf2',
        'neu-shadow-light': '#ffffff',
        'neu-shadow-dark': '#a3b1c6',
        'neu-text': '#2d3748',
        'neu-text-secondary': '#718096',
        // ── Accent ────────────────────────────────────────────────────────
        'neu-accent': '#4a90d9',
        'neu-accent-soft': '#6aaee0',
        'neu-positive': '#48bb78',
        'neu-negative': '#fc8181',
        'neu-warning': '#f6ad55',
        // ── Dark neumorphic palette ────────────────────────────────────────
        'dark-neu-bg': '#1e2130',
        'dark-neu-surface': '#252836',
        'dark-neu-shadow-light': '#2d3250',
        'dark-neu-shadow-dark': '#141622',
        'dark-neu-text': '#e2e8f0',
        'dark-neu-text-secondary': '#94a3b8',
        'dark-neu-accent': '#5bb8f5',
        'dark-neu-positive': '#68d391',
        'dark-neu-negative': '#fc8181',
      },
      borderRadius: {
        'neu-sm': '12px',
        'neu-md': '16px',
        'neu-lg': '24px',
        'neu-xl': '32px',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-in-left': 'slideInLeft 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInLeft: {
          '0%': { opacity: '0', transform: 'translateX(-16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
