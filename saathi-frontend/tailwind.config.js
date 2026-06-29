/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sbi-blue': '#1B3F7A',
        'sbi-dark': '#0F2347',
        'sbi-accent': '#E8A020',
        'sbi-bg': '#F5F6F8',
      }
    },
  },
  plugins: [],
}
