/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        serif: ['Newsreader', 'Georgia', 'Cambria', 'Times New Roman', 'serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      colors: {
        paper: {
          50: '#FDFDFC',
          100: '#FBFBFA',
          200: '#F4F4F0',
          300: '#EAEAE4',
          400: '#DFDFD8',
          500: '#D2D2C8',
        },
        ink: {
          50: '#F4F5F7',
          100: '#E4E6EB',
          200: '#C7CBD4',
          300: '#9EA4B3',
          400: '#6C7385',
          500: '#4D5464',
          600: '#383D4A',
          700: '#2A2E38',
          800: '#1C1F26',
          900: '#111317',
          950: '#0A0B0E',
        },
        court: {
          navy: '#0C1829',
          crimson: '#7F1D1D',
          brass: '#854D0E',
          emerald: '#065F46',
        }
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.04)',
        'elevated': '0 4px 20px -2px rgba(17, 19, 23, 0.06), 0 2px 6px -1px rgba(17, 19, 23, 0.04)',
        'dossier': '0 12px 36px -4px rgba(17, 19, 23, 0.08), 0 4px 12px -2px rgba(17, 19, 23, 0.03)',
      }
    },
  },
  plugins: [],
}
