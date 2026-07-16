import "./globals.css";

export const metadata = {
  title: {
    default: "Mnemos",
    template: "%s · Mnemos",
  },
  description:
    "Evidence-grounded industrial intelligence for reliability, operations, and compliance teams.",
  icons: {
    icon:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='5' fill='%23101114'/%3E%3Cpath d='M6 17V7l6 6 6-6v10' stroke='%232f6fe0' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
