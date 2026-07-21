import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";
import LandingWorkflow from "@/components/public/LandingWorkflow";
import { FadeIn, FloatCard } from "@/components/public/Motion";

const METRICS = [
  ["0.8438", "Weighted evaluation score"],
  ["0.9167", "Citation precision"],
  ["0.9375", "Abstention quality"],
];

const CAPABILITIES = [
  ["Asset-centred memory", "Identity, events, documents, failures, and expert knowledge are resolved around the equipment teams operate."],
  ["Hybrid retrieval", "Vector, lexical, structured, graph, and multi-hop retrieval are fused before evidence reaches the reasoning layer."],
  ["Claim verification", "Answers preserve supporting evidence, contradictions, source revision, confidence, and missing information."],
  ["Durable orchestration", "Checkpoints, idempotency, audit events, and approval state survive process interruption and retry."],
  ["Governed tool use", "Agents operate through scoped tools with allowlists, timeouts, budgets, and retained trajectories."],
  ["Human authority", "Critical RCA, compliance, and knowledge actions pause for authorised review rather than auto-approving."],
];

export default function HomePage() {
  return (
    <PublicShell>
      <main className="public-canvas overflow-hidden">
        <section className="relative isolate flex min-h-[calc(100vh-65px)] items-center overflow-hidden bg-[#111216] text-white">
          <div className="absolute inset-0 -z-20 bg-[url('/brand/industrial-memory-hero.webp')] bg-cover bg-center opacity-35 grayscale" aria-hidden="true" />
          <div className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgba(17,18,22,.72),rgba(17,18,22,.94))]" aria-hidden="true" />
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,.12),transparent_38%)]" aria-hidden="true" />

          <div className="mx-auto w-full max-w-6xl px-5 py-12 text-center sm:px-6 lg:px-8 lg:py-16">
            <FadeIn className="mx-auto max-w-4xl">
              <div className="inline-flex items-center rounded-full border border-white/15 bg-white/[0.05] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#cdd0d7] backdrop-blur">
                Industrial operating memory
              </div>
              <h1 className="mx-auto mt-6 max-w-4xl text-[44px] font-semibold leading-[0.96] tracking-[-0.065em] text-white sm:text-[64px] lg:text-[76px]">
                Operational knowledge that remains usable, reviewable, and accountable.
              </h1>
              <p className="mx-auto mt-6 max-w-3xl text-[15px] leading-7 text-[#cdd0d7] sm:text-[17px]">
                Mnemos connects maintenance records, procedures, inspections, failures, compliance evidence, and field expertise around each asset—then turns that context into traceable decisions.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link href="/dashboard" className="rounded-full bg-white px-5 py-3 text-[13px] font-semibold text-[#111216] transition hover:bg-[#e2e4e9]">Explore the workspace</Link>
                <Link href="/documentation" className="rounded-full border border-white/20 bg-white/[0.04] px-5 py-3 text-[13px] font-semibold text-white transition hover:bg-white/[0.09]">Review the architecture</Link>
              </div>
            </FadeIn>

            <FadeIn delay={0.1} className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 sm:grid-cols-3">
              {METRICS.map(([value, label]) => (
                <div key={label} className="bg-[#111216]/92 px-4 py-4 text-left sm:px-5">
                  <div className="font-mono text-[19px] font-semibold text-white">{value}</div>
                  <div className="mt-1 text-[10.5px] leading-4 text-slate-400">{label}</div>
                </div>
              ))}
            </FadeIn>

            <FadeIn delay={0.16} className="mx-auto mt-7 grid max-w-4xl gap-3 text-left text-[11.5px] text-[#cdd0d7] sm:grid-cols-4">
              {["Evidence-linked conclusions", "Asset and site scope enforced", "Durable human approval", "Provider failures degrade safely"].map((item) => (
                <div key={item} className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 backdrop-blur">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-white" />{item}
                </div>
              ))}
            </FadeIn>
          </div>
        </section>

        <section className="relative mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="max-w-3xl">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.22em] text-slate-500">From fragmented records to governed action</div>
            <h2 className="mt-4 text-[38px] font-semibold leading-tight tracking-[-0.055em] text-[#111216] sm:text-[50px]">
              A working model of how industrial knowledge becomes defensible.
            </h2>
            <p className="mt-5 text-[15px] leading-8 text-slate-600">
              The interface is intentionally simple. Underneath it, Mnemos resolves identity, retrieves across multiple stores, verifies evidence, routes specialist reasoning, and retains the complete execution trail.
            </p>
          </div>
          <div className="mt-10"><LandingWorkflow /></div>
        </section>

        <section className="border-y border-[#e8e2d8] bg-[rgba(246,242,235,0.72)] py-20 backdrop-blur-[2px] lg:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-6 lg:px-8">
            <div className="grid gap-10 lg:grid-cols-[.72fr,1.28fr]">
              <div>
                <div className="text-[10.5px] font-semibold uppercase tracking-[0.22em] text-slate-500">Engineering responses to operational risk</div>
                <h2 className="mt-4 text-[36px] font-semibold tracking-[-0.05em] text-[#111216]">Depth where trust depends on it.</h2>
                <p className="mt-5 text-[14px] leading-7 text-slate-600">Mnemos is designed around failure modes that matter in industrial systems: stale evidence, incorrect identity, hidden contradictions, unbounded tool use, and actions taken without authority.</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {CAPABILITIES.map(([title, text], index) => (
                  <FloatCard key={title} delay={index * 0.04} className="rounded-2xl border border-slate-200 bg-white p-6">
                    <div className="font-mono text-[10px] text-slate-400">0{index + 1}</div>
                    <h3 className="mt-4 text-[17px] font-semibold tracking-[-0.03em] text-[#111216]">{title}</h3>
                    <p className="mt-3 text-[13px] leading-6 text-slate-600">{text}</p>
                  </FloatCard>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="grid gap-10 rounded-[30px] bg-[#111216] px-6 py-10 text-white sm:px-10 lg:grid-cols-[1fr,auto] lg:items-end lg:px-14 lg:py-14">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Explore the product directly</div>
              <h2 className="mt-4 max-w-3xl text-[36px] font-semibold leading-tight tracking-[-0.05em]">Follow an investigation from evidence retrieval to a reviewable decision.</h2>
              <p className="mt-4 max-w-2xl text-[14px] leading-7 text-[#cdd0d7]">The public workspace uses synthetic operational records and remains read-only. Private workspaces are available after authentication.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-full bg-white px-5 py-3 text-[13px] font-semibold text-[#111216]">Open workspace</Link>
              <Link href="/about" className="rounded-full border border-white/20 px-5 py-3 text-[13px] font-semibold text-white">About Mnemos</Link>
            </div>
          </div>
        </section>
      </main>
    </PublicShell>
  );
}
