import edunest from './src/edunest/tailwind-preset.js'

/** @type {import('tailwindcss').Config} */
export default {
  // Colores, fuente, radios y sombras vienen del design system edunest.
  // Para cambiar de marca: data-brand en <html> (ver src/edunest/edunest-theme.css).
  presets: [edunest],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  plugins: [],
}
