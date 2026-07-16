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
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='6' fill='%2317191f'/%3E%3Cpath d='M12 4 19 8v8l-7 4-7-4V8l7-4Z' stroke='%237f8797' stroke-width='1.2' fill='none'/%3E%3Cpath d='M5 8.5 12 12.5 19 8.5M12 12.5V20' stroke='%232f6fe0' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3Ccircle cx='5' cy='8.5' r='1.4' fill='%232f6fe0'/%3E%3Ccircle cx='19' cy='8.5' r='1.4' fill='%232f6fe0'/%3E%3Ccircle cx='12' cy='20' r='1.4' fill='%23eef1f6'/%3E%3C/svg%3E",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
