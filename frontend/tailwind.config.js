/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#060b17',
        surface: 'rgba(255,255,255,0.04)',
        border: 'rgba(255,255,255,0.08)',
        primary: '#6366f1',
        success: '#22c55e',
        warning: '#f59e0b',
        danger: '#ef4444',
        muted: '#6b7280',
        // Aurora palette
        aurora: {
          cyan:   '#22d3ee',
          purple: '#a78bfa',
          pink:   '#f472b6',
          green:  '#34d399',
          blue:   '#60a5fa',
          indigo: '#818cf8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        card:  '14px',
        btn:   '9px',
        input: '7px',
      },
      backdropBlur: {
        glass: '40px',
        heavy: '52px',
      },
      boxShadow: {
        glass:       '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.1)',
        'glass-lg':  '0 12px 48px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.12)',
        'aurora-sm': '0 4px 18px rgba(99,102,241,0.32)',
        'aurora-md': '0 6px 28px rgba(99,102,241,0.48)',
      },
    },
  },
  plugins: [],
}
