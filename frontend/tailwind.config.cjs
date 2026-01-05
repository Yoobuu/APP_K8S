/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html','./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: '#f8fafc',
          card: '#ffffff',
          muted: '#e2e8f0',
          contrast: '#0f172a',
          border: '#d7dde5',
        },
        text: {
          base: '#0f172a',
          muted: '#475569',
          subtle: '#64748b',
        },
        accent: {
          50: '#e0f2fe',
          100: '#bae6fd',
          200: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
      },
      fontSize: {
        table: ['14px', { lineHeight: '20px', letterSpacing: '0' }],
        body: ['15px', { lineHeight: '22px' }],
        label: ['13px', { lineHeight: '18px', letterSpacing: '0.01em' }],
      },
      borderRadius: {
        card: '1rem',
        button: '0.75rem',
        pill: '9999px',
      },
      boxShadow: {
        soft: '0 10px 30px -12px rgba(15, 23, 42, 0.12)',
        card: '0 12px 40px -16px rgba(15, 23, 42, 0.16)',
        modal: '0 24px 70px -18px rgba(15, 23, 42, 0.25)',
      },
    },
  },
  plugins: [],
}
