import PublicShell from "@/components/public/PublicShell";

export const metadata = { title: "About Mnemos" };

export default function AboutPage() {
  return (
    <PublicShell>
      <section className="border-b border-line">
        <div className="mx-auto max-w-7xl px-5 py-20 sm:px-7 lg:px-8">
          <div className="max-w-3xl">
            <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-signal-blue-deep">About</div>
            <h1 className="mt-4 text-[40px] font-semibold leading-[1.1] tracking-[-0.035em] text-ink sm:text-[48px]">Industrial knowledge should survive shifts, systems and staff changes.</h1>
            <p className="mt-6 text-[15px] leading-7 text-ink-soft">Mnemos was designed around a simple observation: plants generate large amounts of operational evidence, but the relationships needed for decisions remain fragmented across documents, systems and human memory.</p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-7 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-[.8fr_1.2fr]">
          <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-ink-faint">The problem</div>
          <div className="space-y-5 text-[15px] leading-7 text-ink-soft">
            <p>Maintenance teams may know that an asset failed before, but not whether the earlier work order included the same condition. Compliance teams may have evidence, but not know that it is superseded or contradictory. Experts carry valuable context that rarely enters formal systems.</p>
            <p>Mnemos turns these disconnected records into an asset-centric operational memory while preserving source provenance and human accountability.</p>
          </div>
        </div>

        <div className="mt-16 grid gap-4 md:grid-cols-3">
          <Value title="Useful before impressive" text="The interface is built for plant users first. Technical depth is documented without crowding daily workflows." />
          <Value title="Evidence before fluency" text="A well-written answer is not enough. Operational claims must be traceable, reviewable and scoped." />
          <Value title="Assistance, not autonomy" text="Mnemos supports decisions. It does not control equipment or replace accountable engineering review." />
        </div>
      </section>

      <section className="border-y border-line bg-paper-alt">
        <div className="mx-auto max-w-7xl px-5 py-16 sm:px-7 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-2">
            <div>
              <h2 className="text-[25px] font-semibold tracking-[-0.02em] text-ink">Who it is for</h2>
              <p className="mt-3 text-[13px] leading-6 text-ink-soft">Reliability engineers, maintenance planners, operations teams, safety teams, quality reviewers and technical leaders working across complex industrial environments.</p>
            </div>
            <div>
              <h2 className="text-[25px] font-semibold tracking-[-0.02em] text-ink">What it is not</h2>
              <p className="mt-3 text-[13px] leading-6 text-ink-soft">It is not a generic document chatbot, a replacement for CMMS/EAM systems, or an autonomous plant-control layer. It connects evidence and workflows those systems leave fragmented.</p>
            </div>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function Value({ title, text }) {
  return <div className="rounded-md border border-line bg-paper p-6"><h3 className="text-[15px] font-semibold text-ink">{title}</h3><p className="mt-3 text-[13px] leading-6 text-ink-soft">{text}</p></div>;
}
