import Link from "next/link";
import Brand from "@/components/public/Brand";

export const metadata = { title: "Sign in to Mnemos" };

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-paper-alt px-5 py-8">
      <div className="mx-auto flex max-w-6xl items-center justify-between"><Brand /><Link href="/" className="text-[12.5px] text-ink-soft hover:text-ink">Back to product</Link></div>
      <div className="mx-auto grid min-h-[calc(100vh-100px)] max-w-6xl items-center gap-12 py-12 lg:grid-cols-2">
        <div className="hidden lg:block">
          <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-signal-blue-deep">Secure workspace access</div>
          <h1 className="mt-4 max-w-xl text-[38px] font-semibold leading-[1.12] tracking-[-0.03em] text-ink">Operational intelligence with site and role boundaries built in.</h1>
          <p className="mt-5 max-w-lg text-[14px] leading-6 text-ink-soft">Access is scoped by organisation, plant, role and evidence classification. Every governed action is auditable.</p>
        </div>
        <div className="mx-auto w-full max-w-md rounded-lg border border-line bg-paper p-6 shadow-pop sm:p-8">
          <div className="text-[11px] font-semibold uppercase tracking-[0.13em] text-ink-faint">Mnemos workspace</div>
          <h2 className="mt-2 text-[24px] font-semibold tracking-[-0.02em] text-ink">Sign in</h2>
          <p className="mt-2 text-[12.5px] leading-5 text-ink-faint">Use your organisation credentials to access authorised sites.</p>
          <form className="mt-7 space-y-4">
            <label className="block"><span className="mb-1.5 block text-[12px] font-medium text-ink-soft">Email</span><input type="email" placeholder="name@company.com" className="w-full rounded-md border border-line-strong bg-paper px-3 py-2.5 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-signal-blue" /></label>
            <label className="block"><span className="mb-1.5 block text-[12px] font-medium text-ink-soft">Password</span><input type="password" placeholder="••••••••••••" className="w-full rounded-md border border-line-strong bg-paper px-3 py-2.5 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-signal-blue" /></label>
            <button type="button" className="w-full rounded-md bg-rail px-4 py-2.5 text-[13px] font-medium text-white hover:bg-rail-raised">Continue</button>
          </form>
          <div className="mt-5 border-t border-line pt-4 text-[11.5px] leading-5 text-ink-faint">Authentication will be connected to the backend session flow during integration. This screen is ready for visual review.</div>
        </div>
      </div>
    </div>
  );
}
