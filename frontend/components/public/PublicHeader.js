"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Brand from "./Brand";

const LINKS = [
  { href: "/documentation", label: "Documentation" },
  { href: "/about", label: "About" },
  { href: "/dashboard", label: "Dashboard" },
];

export default function PublicHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-paper/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="shrink-0">
          <Brand compact />
        </Link>

        <nav className="hidden items-center gap-1 rounded-full border border-line bg-paper-sunk/80 p-1 md:flex">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-4 py-2 text-[12.5px] font-medium transition ${
                  active ? "bg-paper text-ink shadow-sm" : "text-ink-soft hover:text-ink"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Link href="/signin" className="rounded-full px-4 py-2 text-[12.5px] font-medium text-ink-soft transition hover:text-ink">
            Sign in
          </Link>
          <Link href="/signup" className="rounded-full bg-rail px-4 py-2 text-[12.5px] font-medium text-white transition hover:bg-rail-raised">
            Request access
          </Link>
        </div>
      </div>
    </header>
  );
}
