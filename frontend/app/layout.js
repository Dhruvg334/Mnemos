import "./globals.css";

export const metadata = {
  title: {
    default: "Mnemos",
    template: "%s · Mnemos",
  },
  description:
    "Evidence-grounded industrial intelligence for reliability, operations, and compliance teams.",
  icons: {
    icon: "/brand/mnemos-mark.svg",
    shortcut: "/brand/mnemos-mark.svg",
    apple: "/brand/mnemos-mark.svg",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
