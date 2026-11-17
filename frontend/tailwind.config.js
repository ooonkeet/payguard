/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        canvas: '#0A0C10',
        surface: {
          DEFAULT: '#11141B',
          raised: '#161B24',
          hover: '#1C222E',
        },
        border: {
          subtle: '#222836',
          strong: '#2E3648',
        },
      },
    },
  },
  plugins: [],
}

