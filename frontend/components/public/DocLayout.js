import PublicShell from "./PublicShell";
import DocsSidebar from "./DocsSidebar";

export default function DocLayout({ title, eyebrow, summary, children }) {
  return (
    <PublicShell>
      <main className="mx-auto max-w-7xl px-5 py-10 sm:px-6 lg:px-8">
        <header className="mb-10 border-b border-line pb-8">
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-signal-blue">{eyebrow}</div>
          <h1 className="mt-3 max-w-4xl text-[34px] font-semibold leading-[1.05] tracking-[-0.045em] text-ink sm:text-[44px]">{title}</h1>
          <p className="mt-4 max-w-3xl text-[15px] leading-7 text-ink-soft">{summary}</p>
        </header>
        <div className="grid gap-10 xl:grid-cols-[260px,minmax(0,1fr)]">
          <DocsSidebar />
          <div className="prose-doc min-w-0">{children}</div>
        </div>
      </main>
    </PublicShell>
  );
}
