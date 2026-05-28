// design/tokens.ts
// Source of truth for design tokens. Both admin and mini-app import from here.

export const colors = {
  brand: {
    50: '#eef3ff',
    100: '#d6e0ff',
    200: '#aac0ff',
    300: '#7a99ff',
    400: '#4f76ff',
    500: '#2c54ee', // primary
    600: '#1e3fcc',
    700: '#162f9c',
    800: '#11236f',
    900: '#0a164a',
  },
  accent: {
    400: '#ff8a4c',
    500: '#ff6b1f', // CTA accent
    600: '#e0530a',
  },
  neutral: {
    0:   '#ffffff',
    50:  '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a',
  },
  status: {
    success: '#16a34a',
    warning: '#eab308',
    error:   '#dc2626',
    info:    '#0ea5e9',
  },
} as const

export const typography = {
  fontFamily: {
    body: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    heading: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    mono: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace',
  },
  fontSize: {
    xs:   '0.75rem',   // 12
    sm:   '0.875rem',  // 14
    base: '1rem',      // 16
    lg:   '1.125rem',  // 18
    xl:   '1.25rem',   // 20
    '2xl': '1.5rem',   // 24
    '3xl': '1.875rem', // 30
    '4xl': '2.25rem',  // 36
    '5xl': '3rem',     // 48
  },
  fontWeight: { regular: 400, medium: 500, semibold: 600, bold: 700 },
  lineHeight: { tight: 1.2, snug: 1.35, normal: 1.5, relaxed: 1.7 },
} as const

export const spacing = {
  0: '0', 1: '0.25rem', 2: '0.5rem', 3: '0.75rem', 4: '1rem',
  5: '1.25rem', 6: '1.5rem', 8: '2rem', 10: '2.5rem', 12: '3rem',
  16: '4rem', 20: '5rem', 24: '6rem',
} as const

export const radius = {
  none: '0', sm: '0.25rem', md: '0.5rem', lg: '0.75rem', xl: '1rem',
  '2xl': '1.5rem', full: '9999px',
} as const

export const shadow = {
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  inner: 'inset 0 2px 4px 0 rgb(0 0 0 / 0.05)',
} as const

export const transition = {
  fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
  base: '250ms cubic-bezier(0.4, 0, 0.2, 1)',
  slow: '400ms cubic-bezier(0.4, 0, 0.2, 1)',
} as const
