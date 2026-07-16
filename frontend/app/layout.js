import "./globals.css";

export const metadata = {
  title: { default: "Mnemos — Industrial Knowledge Intelligence", template: "%s · Mnemos" },
  description: "Evidence-grounded asset intelligence for industrial reliability teams.",
  icons: {
    icon:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='5' fill='%23101114'/%3E%3Cpath d='M6 17V7l6 6 6-6v10' stroke='%232f6fe0' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="true" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        <style>{`:root{ --font-ui: 'IBM Plex Sans', -apple-system, sans-serif; --font-mono: 'IBM Plex Mono', ui-monospace, monospace; }`}</style>
      </head>
      <body>{children}</body>
    </html>
  );
}
