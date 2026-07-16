"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import Brand from "./Brand";

function validate(mode, values) {
  const errors = {};
  if (!values.email.trim()) errors.email = "Email is required.";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) errors.email = "Enter a valid work email.";

  if (!values.password.trim()) errors.password = "Password is required.";
  else if (values.password.length < 8) errors.password = "Use at least 8 characters.";

  if (mode === "signup") {
    if (!values.name.trim()) errors.name = "Full name is required.";
    if (!values.organization.trim()) errors.organization = "Organization is required.";
    if (!values.confirmPassword.trim()) errors.confirmPassword = "Confirm your password.";
    else if (values.confirmPassword !== values.password) errors.confirmPassword = "Passwords do not match.";
  }
  return errors;
}

export default function AuthForm({ initialMode = "signin" }) {
  const [mode, setMode] = useState(initialMode);
  const [values, setValues] = useState({ name: "", organization: "", email: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const isSignup = mode === "signup";

  const statusText = useMemo(() => {
    if (!submitted) return null;
    return isSignup
      ? "Validation passed. Backend email verification will be connected during authentication integration."
      : "Validation passed. Backend session creation will be connected during authentication integration.";
  }, [submitted, isSignup]);

  function switchMode(nextMode) {
    setMode(nextMode);
    setErrors({});
    setSubmitted(false);
  }

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

  const fieldClass = (name) => `mt-1.5 w-full rounded-xl border bg-paper px-3.5 py-2.5 text-[13px] text-ink outline-none transition placeholder:text-ink-faint ${errors[name] ? "border-signal-red bg-signal-red-pale/40" : "border-line focus:border-signal-blue"}`;

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper-alt px-5 py-6">
      <div className="motion-fade-up w-full max-w-[620px] rounded-[28px] border border-line bg-paper p-6 shadow-pop sm:p-7">
        <div className="flex items-center justify-between gap-4">
          <Link href="/"><Brand compact /></Link>
          <Link href="/" className="text-[12px] text-ink-faint transition hover:text-ink">Back home</Link>
        </div>

        <div className="mt-6 flex rounded-xl border border-line bg-paper-alt p-1">
          {[
            ["signin", "Sign in"],
            ["signup", "Create account"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => switchMode(value)}
              className={`flex-1 rounded-lg px-4 py-2 text-[12.5px] font-medium transition ${mode === value ? "bg-paper text-ink shadow-sm" : "text-ink-faint hover:text-ink"}`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="mt-5">
          <div className="text-[10.5px] font-semibold uppercase tracking-[0.2em] text-signal-blue">{isSignup ? "Workspace access" : "Secure access"}</div>
          <h1 className="mt-2 text-[25px] font-semibold tracking-[-0.04em] text-ink">{isSignup ? "Create your Mnemos workspace" : "Welcome back"}</h1>
          <p className="mt-2 text-[13px] leading-6 text-ink-soft">
            {isSignup ? "Create a site-scoped workspace for governed industrial knowledge." : "Access your approved plants, assets, investigations, and evidence."}
          </p>
        </div>

        <form className="mt-5 grid gap-3" onSubmit={handleSubmit} noValidate>
          {isSignup ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Full name" error={errors.name}>
                <input className={fieldClass("name")} value={values.name} onChange={(e) => update("name", e.target.value)} placeholder="Dhruv Gupta" />
              </Field>
              <Field label="Organization" error={errors.organization}>
                <input className={fieldClass("organization")} value={values.organization} onChange={(e) => update("organization", e.target.value)} placeholder="North Process Plant" />
              </Field>
            </div>
          ) : null}

          <Field label="Work email" error={errors.email}>
            <input type="email" className={fieldClass("email")} value={values.email} onChange={(e) => update("email", e.target.value)} placeholder="dhruv@plantops.com" />
          </Field>

          <div className={`grid gap-3 ${isSignup ? "sm:grid-cols-2" : ""}`}>
            <Field label="Password" error={errors.password}>
              <input type="password" className={fieldClass("password")} value={values.password} onChange={(e) => update("password", e.target.value)} placeholder="••••••••" />
            </Field>
            {isSignup ? (
              <Field label="Confirm password" error={errors.confirmPassword}>
                <input type="password" className={fieldClass("confirmPassword")} value={values.confirmPassword} onChange={(e) => update("confirmPassword", e.target.value)} placeholder="••••••••" />
              </Field>
            ) : null}
          </div>

          <button type="submit" className="mt-1 rounded-full bg-rail px-5 py-2.5 text-[12.5px] font-medium text-white transition hover:bg-rail-raised">
            {isSignup ? "Create workspace" : "Sign in"}
          </button>
          <button type="button" className="rounded-full border border-line bg-paper px-5 py-2.5 text-[12.5px] font-medium text-ink transition hover:bg-paper-alt">
            Continue with email link
          </button>
        </form>

        {statusText ? <div className="mt-3 rounded-xl border border-signal-blue-line bg-signal-blue-pale px-3.5 py-2.5 text-[12px] leading-5 text-signal-blue-deep">{statusText}</div> : null}
        <div className="mt-4 text-center text-[11.5px] text-ink-faint">Email verification, refresh-token handling, and account recovery connect in the auth integration phase.</div>
      </div>
    </div>
  );
}

function Field({ label, error, children }) {
  return (
    <label className="block text-[11.5px] font-medium text-ink-soft">
      {label}
      {children}
      {error ? <span className="mt-1 block text-[11.5px] text-signal-red">{error}</span> : null}
    </label>
  );
}
