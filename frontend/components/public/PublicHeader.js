import Link from "next/link";
import Brand from "./Brand";

const links = [
  ["Product", "/#product"],
  ["How it works", "/how-it-works"],
  ["About", "/about"],
];

export default function PublicHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center px-5 sm:px-7 lg:px-8">
        <Brand />
        <nav className="ml-10 hidden items-center gap-7 md:flex" aria-label="Primary navigation">
          {links.map(([label, href]) => (
            <Link key={label} href={href} className="text-[13px] font-medium text-ink-soft transition hover:text-ink">
              {label}
            </Link>
          ))}
        </nav>
        <div className="flex-1" />
        <div className="flex items-center gap-2.5">
          <Link href="/login" className="hidden rounded-md px-3 py-2 text-[13px] font-medium text-ink-soft hover:bg-paper-alt sm:inline-flex">
            Sign in
          </Link>
          <Link href="/dashboard" className="inline-flex rounded-md bg-rail px-3.5 py-2 text-[13px] font-medium text-white transition hover:bg-rail-raised">
            Open workspace
          </Link>
        </div>
      </div>
    </header>
  );
}
