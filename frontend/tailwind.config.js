/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        surface: '#141A26',
        border: '#22304A',
        primary: '#A970FF',
        success: '#00D68F',
        warning: '#FFB020',
        error: '#FF5A5F',
      },
      fontFamily: {
        sans: ['Inter', 'Geist', 'SF Pro', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
