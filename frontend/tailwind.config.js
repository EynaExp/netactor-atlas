/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          50: '#eef7ff',
          100: '#d9edff',
          200: '#bce0ff',
          300: '#8eccff',
          400: '#59b0ff',
          500: '#3b8dff',
          600: '#246df5',
          700: '#1b57e1',
          800: '#1d47b6',
          900: '#1e3f8f',
          950: '#172857',
        },
        dark: {
          50: '#f5f5f5',
          100: '#e5e5e5',
          200: '#c8c8c8',
          300: '#a3a3a3',
          400: '#7a7a7a',
          500: '#5c5c5c',
          600: '#444444',
          700: '#2e2e2e',
          800: '#171717',
          900: '#0a0a0a',
          950: '#000000',
        },
        neon: {
          blue: '#3b8dff',
          purple: '#a855f7',
          green: '#ffffff',
          red: '#ef4444',
          yellow: '#eab308',
          orange: '#f97316',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'slide-in': 'slide-in 0.3s ease-out',
        'fade-in': 'fade-in 0.5s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
        'spin-slow': 'spin 3s linear infinite',
        'bounce-gentle': 'bounce-gentle 2s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'flow-line': 'flow-line 2s linear infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(59, 141, 255, 0.3)' },
          '50%': { boxShadow: '0 0 20px rgba(59, 141, 255, 0.6)' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'bounce-gentle': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'flow-line': {
          '0%': { strokeDashoffset: '20' },
          '100%': { strokeDashoffset: '0' },
        },
      },
      backgroundSize: {
        'shimmer': '200% 100%',
      }
    },
  },
  plugins: [],
}
