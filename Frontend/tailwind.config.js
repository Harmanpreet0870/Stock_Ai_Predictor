/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#060c1a',
        surface: {
          DEFAULT: '#0d1728',
          2: '#111e33',
          3: '#16243d',
        },
        rim: '#1c2e4a',
        bullish: '#00c77a',
        bearish: '#f43f5e',
        hold: '#f59e0b',
        primary: {
          DEFAULT: '#1d6feb',
          light: '#3b82f6',
          dim: '#1d6feb33',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'monospace'],
      },
      keyframes: {
        fadeIn: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        pulse2: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.4' } },
      },
      animation: {
        fadeIn: 'fadeIn 0.3s ease-out',
        pulse2: 'pulse2 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
