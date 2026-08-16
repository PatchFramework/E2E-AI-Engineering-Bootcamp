/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f5f7fa',
          100: '#eaeef4',
          200: '#d0daf2',
          300: '#a3bae3',
          400: '#7093cd',
          500: '#4c73b3',
          600: '#3a5993',
          700: '#304977',
          800: '#2b3f62',
          900: '#263652',
        }
      }
    },
  },
  plugins: [],
}
