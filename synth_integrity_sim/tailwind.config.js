/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bank: {
          deep: '#2f195f',
          soft: '#f6f3ff',
          border: '#ddd4ff',
        },
        attacker: {
          bg: '#0b1220',
          panel: '#111c2f',
          border: '#1f3048',
          accent: '#32d583',
        },
      },
      boxShadow: {
        pane: '0 12px 28px rgba(25, 16, 53, 0.12)',
      },
    },
  },
  plugins: [],
}
