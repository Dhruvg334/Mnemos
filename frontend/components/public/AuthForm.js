"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import Brand from "./Brand";

function validate(mode, values) {
  const errors = {};
  if (!values.email.trim()) {
    errors.email = "Email is required.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
    errors.email = "Enter a valid work email.";
  }

  if (!values.password.trim()) {
    errors.password = "Password is required.";
  } else if (values.password.length < 8) {
    errors.password = "Password must contain at least 8 characters.";
  }

  if (mode === "signup") {
    if (!values.name.trim()) {
      errors.name = "Full name is required.";
    }
    if (!values.organization.trim()) {
      errors.organization = "Organization is required.";
    }
    if (!values.confirmPassword.trim()) {
      errors.confirmPassword = "Please confirm the password.";
    } else if (values.confirmPassword !== values.password) {
      errors.confirmPassword = "Passwords do not match.";
    }
  }

  return errors;
}

export default function AuthForm({ mode = "signin" }) {
  const [values, setValues] = useState({
    name: "",
    organization: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [errors, setErrors] = useState({});
  const [submitted, setSubmitted] = useState(false);

  const isSignup = mode === "signup";
  const title = isSignup ? "Create your Mnemos workspace" : "Sign in to Mnemos";
  const subtitle = isSignup
    ? "Start with controlled email access, asset-scoped workspaces, and an operator-facing reliability dashboard."
    : "Use your approved work email to access site-scoped evidence, investigations, and operational knowledge.";

  const statusText = useMemo(() => {
    if (!submitted) return null;
    return isSignup
      ? "Validation passed. Workspace creation will be wired to backend email authentication in the next integration phase."
      : "Validation passed. Sign-in submission will be wired to backend email authentication in the next integration phase.";
  }, [submitted, isSignup]);

  function update(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validate(mode, values);
    setErrors(nextErrors);
    setSubmitted(Object.keys(nextErrors).length === 0);
  }

  const fieldClass = (name) =>
    `mt-2 w-full rounded-2xl border bg-paper px-4 py-3 text-[14px] text-ink outline-none transition placeholder:text-ink-faint ${
      errors[name] ? "border-signal-red bg-signal-red-pale/50" : "border-line focus:border-signal-blue"
    }`;

  return (
    <div className="grid min-h-screen lg:grid-cols-[0.95fr,1.05fr]">
      <div className="hidden border-r border-line bg-rail text-white lg:block">
        <div className="flex h-full flex-col justify-between p-10">
          <Brand compact />
          <div>
            <div className="max-w-xl text-[34px] font-semibold tracking-[-0.05em]">A cleaner operating memory for industrial teams.</div>
            <div className="mt-5 max-w-lg text-[14px] leading-7 text-rail-soft">
              Mnemos combines governed document intelligence, asset history, graph-linked evidence, and expert knowledge into a product that plant teams can actually use.
            </div>
            <div className="mt-8 grid gap-4">
              {[
                "Evidence-linked asset passports with revision-aware provenance.",
                "Investigations grounded in claims, contradictions, and missing evidence.",
                "Governed knowledge capture across reliability, operations, and compliance.",
              ].map((item) => (
                <div key={item} className="rounded-2xl border border-rail-line bg-rail-raised px-4 py-4 text-[13px] text-rail-ink">
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="text-[12px] text-rail-soft">North Process Plant · South Utilities Plant · role-scoped access</div>
        </div>
      </div>

      <div className="flex min-h-screen items-center justify-center bg-paper-alt px-5 py-10 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.2, 0.65, 0.3, 1] }}
          className="w-full max-w-xl rounded-[32px] border border-line bg-paper p-8 shadow-pop sm:p-10"
        >
          <div className="lg:hidden">
            <Brand />
          </div>
          <div className="mt-5 text-[11px] font-semibold uppercase tracking-[0.22em] text-signal-blue">{isSignup ? "Request access" : "Secure access"}</div>
          <h1 className="mt-3 text-[30px] font-semibold tracking-[-0.04em] text-ink">{title}</h1>
          <p className="mt-3 text-[14px] leading-7 text-ink-soft">{subtitle}</p>

          <form className="mt-8 grid gap-4" onSubmit={handleSubmit} noValidate>
            {isSignup ? (
              <>
                <div>
                  <label className="text-[12px] font-medium text-ink-soft">Full name</label>
                  <input className={fieldClass("name")} value={values.name} onChange={(e) => update("name", e.target.value)} placeholder="Dhruv Gupta" />
                  {errors.name ? <div className="mt-1 text-[12px] text-signal-red">{errors.name}</div> : null}
                </div>
                <div>
                  <label className="text-[12px] font-medium text-ink-soft">Organization</label>
                  <input className={fieldClass("organization")} value={values.organization} onChange={(e) => update("organization", e.target.value)} placeholder="North Process Plant" />
                  {errors.organization ? <div className="mt-1 text-[12px] text-signal-red">{errors.organization}</div> : null}
                </div>
              </>
            ) : null}

            <div>
              <label className="text-[12px] font-medium text-ink-soft">Work email</label>
              <input type="email" className={fieldClass("email")} value={values.email} onChange={(e) => update("email", e.target.value)} placeholder="dhruv@plantops.com" />
              {errors.email ? <div className="mt-1 text-[12px] text-signal-red">{errors.email}</div> : null}
            </div>

            <div>
              <label className="text-[12px] font-medium text-ink-soft">Password</label>
              <input type="password" className={fieldClass("password")} value={values.password} onChange={(e) => update("password", e.target.value)} placeholder="••••••••" />
              {errors.password ? <div className="mt-1 text-[12px] text-signal-red">{errors.password}</div> : null}
            </div>

            {isSignup ? (
              <div>
                <label className="text-[12px] font-medium text-ink-soft">Confirm password</label>
                <input type="password" className={fieldClass("confirmPassword")} value={values.confirmPassword} onChange={(e) => update("confirmPassword", e.target.value)} placeholder="••••••••" />
                {errors.confirmPassword ? <div className="mt-1 text-[12px] text-signal-red">{errors.confirmPassword}</div> : null}
              </div>
            ) : null}

            <button type="submit" className="mt-2 rounded-full bg-rail px-5 py-3 text-[13px] font-medium text-white transition hover:bg-rail-raised">
              {isSignup ? "Create workspace" : "Sign in"}
            </button>

            <button type="button" className="rounded-full border border-line bg-paper px-5 py-3 text-[13px] font-medium text-ink transition hover:bg-paper-alt">
              Continue with email link
            </button>
          </form>

          {statusText ? <div className="mt-4 rounded-2xl border border-signal-blue-line bg-signal-blue-pale px-4 py-3 text-[12.5px] leading-6 text-signal-blue-deep">{statusText}</div> : null}

          <div className="mt-6 flex flex-wrap items-center gap-3 text-[12.5px] text-ink-soft">
            {isSignup ? (
              <>
                <span>Already have an account?</span>
                <Link href="/signin" className="font-medium text-ink hover:text-signal-blue">Sign in</Link>
              </>
            ) : (
              <>
                <span>Need a workspace?</span>
                <Link href="/signup" className="font-medium text-ink hover:text-signal-blue">Create one</Link>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
