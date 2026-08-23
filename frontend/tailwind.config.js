/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        // Primary & accent read from CSS variables (see index.css) so the whole
        // app can be re-themed at runtime via the [data-theme] attribute,
        // without any component needing to change its classnames.
        primary: {
          50: 'rgb(var(--color-primary-50) / <alpha-value>)',
          100: 'rgb(var(--color-primary-100) / <alpha-value>)',
          200: 'rgb(var(--color-primary-200) / <alpha-value>)',
          300: 'rgb(var(--color-primary-300) / <alpha-value>)',
          400: 'rgb(var(--color-primary-400) / <alpha-value>)',
          500: 'rgb(var(--color-primary-500) / <alpha-value>)',
          600: 'rgb(var(--color-primary-600) / <alpha-value>)',
          700: 'rgb(var(--color-primary-700) / <alpha-value>)',
          800: 'rgb(var(--color-primary-800) / <alpha-value>)',
          900: 'rgb(var(--color-primary-900) / <alpha-value>)',
          950: 'rgb(var(--color-primary-950) / <alpha-value>)',
        },
        accent: {
          50: 'rgb(var(--color-accent-50) / <alpha-value>)',
          100: 'rgb(var(--color-accent-100) / <alpha-value>)',
          200: 'rgb(var(--color-accent-200) / <alpha-value>)',
          300: 'rgb(var(--color-accent-300) / <alpha-value>)',
          400: 'rgb(var(--color-accent-400) / <alpha-value>)',
          500: 'rgb(var(--color-accent-500) / <alpha-value>)',
          600: 'rgb(var(--color-accent-600) / <alpha-value>)',
          700: 'rgb(var(--color-accent-700) / <alpha-value>)',
          800: 'rgb(var(--color-accent-800) / <alpha-value>)',
          900: 'rgb(var(--color-accent-900) / <alpha-value>)',
          950: 'rgb(var(--color-accent-950) / <alpha-value>)',
        },
        // Deep blue-black neutral scale — stays constant across color themes
        dark: {
          50: '#f4f7fb',
          100: '#e6ebf5',
          200: '#c9d3e5',
          300: '#a1aecb',
          400: '#7382a3',
          500: '#556280',
          600: '#404b66',
          700: '#2b3350',
          800: '#181f36',
          900: '#0d1224',
          950: '#040611',
        }
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      boxShadow: {
        'glow': '0 0 20px rgb(var(--color-primary-400) / 0.35)',
        'glow-sm': '0 0 10px rgb(var(--color-primary-400) / 0.3)',
        'glow-lg': '0 0 40px rgb(var(--color-primary-400) / 0.25)',
        'glow-accent': '0 0 25px rgb(var(--color-accent-500) / 0.35)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255,255,255,0.06)',
        'card': '0 4px 24px -8px rgba(0, 0, 0, 0.5)',
      },
      backgroundImage: {
        'grid-pattern': 'linear-gradient(rgb(var(--color-primary-400) / 0.06) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--color-primary-400) / 0.06) 1px, transparent 1px)',
        'gradient-cyber': 'linear-gradient(135deg, rgb(var(--color-primary-600)) 0%, rgb(var(--color-accent-700)) 100%)',
        'gradient-radial-glow': 'radial-gradient(circle at 50% 0%, rgb(var(--color-primary-400) / 0.15), transparent 60%)',
        'noise': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 60 60'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E\")",
      },
      backgroundSize: {
        'grid': '32px 32px',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'border-glow': {
          '0%, 100%': { borderColor: 'rgb(var(--color-primary-400) / 0.3)' },
          '50%': { borderColor: 'rgb(var(--color-accent-400) / 0.3)' },
        },
        'spin-slow': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'spin-slower-reverse': {
          '0%': { transform: 'rotate(360deg)' },
          '100%': { transform: 'rotate(0deg)' },
        },
      },
      animation: {
        'pulse-glow': 'pulse-glow 2.5s ease-in-out infinite',
        'float': 'float 4s ease-in-out infinite',
        'shimmer': 'shimmer 2.5s linear infinite',
        'scan-line': 'scan-line 3s linear infinite',
        'fade-in-up': 'fade-in-up 0.4s ease-out',
        'border-glow': 'border-glow 3s ease-in-out infinite',
        'spin-slow': 'spin-slow 40s linear infinite',
        'spin-slower': 'spin-slower-reverse 70s linear infinite',
      },
    },
  },
  plugins: [],
}
