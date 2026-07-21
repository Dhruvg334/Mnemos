import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";
import LandingWorkflow from "@/components/public/LandingWorkflow";
import { FadeIn, FloatCard } from "@/components/public/Motion";

const METRICS = [
  ["0.8438", "Weighted evaluation score"],
  ["1.0000", "Retrieval recall"],
  ["0.9167", "Citation precision"],
  ["1.0000", "Grounded-answer rate"],
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
      <main className="overflow-hidden bg-white">
        <section className="relative isolate min-h-[720px] overflow-hidden bg-[#061421] text-white">
          <div className="absolute inset-0 -z-20 bg-[url('/brand/industrial-memory-hero.webp')] bg-cover bg-[65%_center] opacity-70" aria-hidden="true" />
          <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,#061421_0%,rgba(6,20,33,.97)_35%,rgba(6,20,33,.72)_62%,rgba(6,20,33,.54)_100%)]" aria-hidden="true" />
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_75%_20%,rgba(255,255,255,.13),transparent_26%)]" aria-hidden="true" />

          <div className="mx-auto grid max-w-7xl gap-12 px-5 pb-14 pt-20 sm:px-6 lg:grid-cols-[1.05fr,.95fr] lg:px-8 lg:pb-20 lg:pt-28">
            <FadeIn className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-slate-300 backdrop-blur">
                Industrial operating memory
              </div>
              <h1 className="mt-7 text-[48px] font-semibold leading-[0.98] tracking-[-0.065em] text-white sm:text-[70px] lg:text-[78px]">
                Operational knowledge that survives the shift change.
              </h1>
              <p className="mt-7 max-w-2xl text-[16px] leading-8 text-slate-300 sm:text-[17px]">
                Mnemos connects maintenance records, procedures, inspections, failures, compliance evidence, and field expertise around each asset—then turns that context into traceable decisions.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link href="/dashboard" className="rounded-full bg-white px-5 py-3 text-[13px] font-semibold text-[#071522] transition hover:bg-slate-200">Explore the live workspace</Link>
                <Link href="/documentation" className="rounded-full border border-white/20 bg-white/[0.04] px-5 py-3 text-[13px] font-semibold text-white transition hover:bg-white/[0.09]">Review the architecture</Link>
              </div>
              <div className="mt-10 grid max-w-2xl gap-3 text-[12px] text-slate-300 sm:grid-cols-2">
                {[
                  "Evidence-linked conclusions",
                  "Asset and site scope enforced",
                  "Durable human approval",
                  "Provider failures degrade safely",
                ].map((item) => (
                  <div key={item} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-white" />{item}
                  </div>
                ))}
              </div>
            </FadeIn>

            <FadeIn delay={0.12} className="self-end lg:pl-8">
              <div className="rounded-[26px] border border-white/15 bg-[#071522]/78 p-4 shadow-2xl backdrop-blur-xl sm:p-5">
                <div className="flex items-center justify-between border-b border-white/10 pb-4">
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Current investigation</div>
                    <div className="mt-1 text-[15px] font-semibold text-white">P-117 · recurring seal failure</div>
                  </div>
                  <span className="rounded-full border border-white/15 px-2.5 py-1 text-[10px] text-slate-300">Evidence review</span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {[["11", "events"], ["6", "sources"], ["3", "hypotheses"]].map(([value, label]) => (
                    <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-[26px] font-semibold text-white">{value}</div>
                      <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-400">{label}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Leading mechanism</div>
                  <div className="mt-2 text-[14px] font-semibold text-white">Coupling misalignment with foundation soft-foot</div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full w-[84%] rounded-full bg-white" /></div>
                  <div className="mt-2 flex justify-between text-[10px] text-slate-400"><span>8 supporting records</span><span>84% confidence</span></div>
                </div>
              </div>
            </FadeIn>
          </div>

          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-px border-y border-white/10 bg-white/10 sm:grid-cols-4">
            {METRICS.map(([value, label]) => (
              <div key={label} className="bg-[#071522]/90 px-5 py-5 sm:px-7">
                <div className="font-mono text-[20px] font-semibold text-white">{value}</div>
                <div className="mt-1 text-[11px] leading-5 text-slate-400">{label}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="max-w-3xl">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.22em] text-slate-500">From fragmented records to governed action</div>
            <h2 className="mt-4 text-[38px] font-semibold leading-tight tracking-[-0.055em] text-[#071522] sm:text-[50px]">
              A working model of how industrial knowledge becomes defensible.
            </h2>
            <p className="mt-5 text-[15px] leading-8 text-slate-600">
              The interface is intentionally simple. Underneath it, Mnemos resolves identity, retrieves across multiple stores, verifies evidence, routes specialist reasoning, and retains the complete execution trail.
            </p>
          </div>
          <div className="mt-10"><LandingWorkflow /></div>
        </section>

        <section className="bg-[#f4f6f8] py-20 lg:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-6 lg:px-8">
            <div className="grid gap-10 lg:grid-cols-[.72fr,1.28fr]">
              <div>
                <div className="text-[10.5px] font-semibold uppercase tracking-[0.22em] text-slate-500">Engineering responses to operational risk</div>
                <h2 className="mt-4 text-[36px] font-semibold tracking-[-0.05em] text-[#071522]">Depth where trust depends on it.</h2>
                <p className="mt-5 text-[14px] leading-7 text-slate-600">Mnemos is designed around failure modes that matter in industrial systems: stale evidence, incorrect identity, hidden contradictions, unbounded tool use, and actions taken without authority.</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {CAPABILITIES.map(([title, text], index) => (
                  <FloatCard key={title} delay={index * 0.04} className="rounded-2xl border border-slate-200 bg-white p-6">
                    <div className="font-mono text-[10px] text-slate-400">0{index + 1}</div>
                    <h3 className="mt-4 text-[17px] font-semibold tracking-[-0.03em] text-[#071522]">{title}</h3>
                    <p className="mt-3 text-[13px] leading-6 text-slate-600">{text}</p>
                  </FloatCard>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="grid gap-10 rounded-[30px] bg-[#071522] px-6 py-10 text-white sm:px-10 lg:grid-cols-[1fr,auto] lg:items-end lg:px-14 lg:py-14">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Explore the product directly</div>
              <h2 className="mt-4 max-w-3xl text-[36px] font-semibold leading-tight tracking-[-0.05em]">Follow an investigation from evidence retrieval to a reviewable decision.</h2>
              <p className="mt-4 max-w-2xl text-[14px] leading-7 text-slate-300">The public workspace uses synthetic operational records and remains read-only. Private workspaces are available after authentication.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-full bg-white px-5 py-3 text-[13px] font-semibold text-[#071522]">Open workspace</Link>
              <Link href="/about" className="rounded-full border border-white/20 px-5 py-3 text-[13px] font-semibold text-white">About Mnemos</Link>
            </div>
          </div>
        </section>
      </main>
    </PublicShell>
  );
}
