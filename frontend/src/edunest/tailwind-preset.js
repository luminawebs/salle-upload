/**
 * edunest · preset de Tailwind (v3)
 * Uso en tailwind.config.js:
 *   import edunest from './edunest/tailwind-preset.js'
 *   export default { presets: [edunest], content: [...] }
 * y carga edunest-theme.css (las variables --en-*) en tu CSS de entrada.
 * Cambiar de marca = poner data-brand="camara" | "poli" | "lasalle" en <html>.
 * Las clases son las mismas en todos los productos: bg-background, bg-surface,
 * border-border, bg-primary text-on-primary, text-heading, text-muted…
 */
const c = (v) => `rgb(var(--en-${v}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    extend: {
      colors: {
        background: c('bg'),
        surface: { DEFAULT: c('surface'), raised: c('surface-raised') },
        border: { DEFAULT: c('border'), control: c('border-control') },
        heading: c('heading'),
        text: c('text'),
        muted: c('text-muted'),
        subtle: c('text-subtle'),
        primary: { DEFAULT: c('primary'), hover: c('primary-hover'), text: c('primary-text') },
        'on-primary': c('on-primary'),
        focus: c('focus'),
        success: c('success'),
        warning: c('warning'),
        error: c('error'),
        // Identidad edunest fija (logo, piezas), no cambia con data-brand
        brand: { navy: '#031119', slate: '#1b262c', amber: '#e3a127', yellow: '#ffbf2a', mist: '#e0e9f2' },
      },
      fontFamily: {
        sans: ['var(--en-font-sans)'],
      },
      borderRadius: {
        DEFAULT: 'var(--en-radius-control)',
        card: 'var(--en-radius)',
        pill: 'var(--en-radius-pill)',
      },
      boxShadow: {
        card: '0 4px 20px rgba(0, 0, 0, 0.1)',
        'card-hover': '0 8px 30px rgba(0, 0, 0, 0.15)',
        accent: '0 4px 15px rgb(var(--en-primary) / 0.3)',
      },
      transitionDuration: { DEFAULT: '300ms' },
    },
  },
};
