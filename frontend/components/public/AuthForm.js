"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Brand from "./Brand";

function validate(mode, values) {
  const errors = {};
  if (!values.email.trim()) errors.email = "Email is required.";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) errors.email = "Enter a valid work email.";

  if (!values.password.trim()) errors.password = "Password is required.";
  else if (values.password.length < (mode === "signup" ? 12 : 1)) errors.password = mode === "signup" ? "Use at least 12 characters." : "Password is required.";

  if (mode === "signup") {
    if (!values.name.trim()) errors.name = "Full name is required.";
    if (!values.organization.trim()) errors.organization = "Organization is required.";
    if (!values.confirmPassword.trim()) errors.confirmPassword = "Confirm your password.";
    else if (values.confirmPassword !== values.password) errors.confirmPassword = "Passwords do not match.";
    if (values.password && !/[a-z]/.test(values.password)) errors.password = "Include a lowercase letter.";
    else if (values.password && !/[A-Z]/.test(values.password)) errors.password = "Include an uppercase letter.";
    else if (values.password && !/\d/.test(values.password)) errors.password = "Include a number.";
    else if (values.password && !/[^A-Za-z0-9]/.test(values.password)) errors.password = "Include a symbol.";
  }
  return errors;
}

function normalizeError(payload, fallback) {
  const fieldErrors = {};
  const fields = payload?.error?.details?.fields || [];
  for (const field of fields) {
    if (field.field) fieldErrors[field.field] = field.message;
  }
  return {
    fieldErrors,
    message: payload?.error?.message || fallback,
  };
}

export default function AuthForm({ initialMode = "signin" }) {
  const router = useRouter();
  const [mode, setMode] = useState(initialMode);
  const [values, setValues] = useState({ name: "", organization: "", email: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const isSignup = mode === "signup";

  function switchMode(nextMode) {
    setMode(nextMode);
    setErrors({});
    setStatus(null);
  }

  function update(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
    setStatus(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validate(mode, values);
    setErrors(nextErrors);
    setStatus(null);
    if (Object.keys(nextErrors).length) return;

    setSubmitting(true);
    let navigationStarted = false;
    try {
      const response = await fetch(isSignup ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          isSignup
            ? {
                full_name: values.name,
                organisation_name: values.organization,
                email: values.email,
                password: values.password,
              }
            : { email: values.email, password: values.password },
        ),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const parsed = normalizeError(payload, "Authentication could not be completed.");
        setErrors(parsed.fieldErrors);
        setStatus({ tone: "error", message: parsed.message });
        return;
      }
      navigationStarted = true;
      setRedirecting(true);
      router.replace("/dashboard");
      router.refresh();
    } catch {
      setStatus({ tone: "error", message: "The authentication service is unavailable. Check that the backend is running." });
    } finally {
      if (!navigationStarted) setSubmitting(false);
    }
  }

  const fieldClass = (name) => `mt-1.5 w-full rounded-xl border bg-paper px-3.5 py-2.5 text-[13px] text-ink outline-none transition placeholder:text-ink-faint ${errors[name] ? "border-signal-red bg-signal-red-pale/40" : "border-line focus:border-strong"}`;

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper-alt px-5 py-6">
      <div className="motion-fade-up w-full max-w-[620px] rounded-[28px] border border-line bg-paper p-6 shadow-pop sm:p-7">
        <div className="flex items-center justify-between gap-4">
          <Link href="/"><Brand compact /></Link>
          <Link href="/" className="text-[12px] text-ink-faint transition hover:text-ink">Back home</Link>
        </div>

        <div className="mt-6 flex rounded-xl border border-line bg-paper-alt p-1" role="tablist" aria-label="Authentication mode">
          {[["signin", "Sign in"], ["signup", "Create account"]].map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => switchMode(value)}
              className={`flex-1 rounded-lg px-4 py-2 text-[12.5px] font-medium transition ${mode === value ? "bg-paper text-ink shadow-sm" : "text-ink-faint hover:text-ink"}`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="mt-5">
          <div className="text-[10.5px] font-semibold uppercase tracking-[0.2em] text-ink">{isSignup ? "Create your workspace" : "Secure access"}</div>
          <h1 className="mt-2 text-[25px] font-semibold tracking-[-0.04em] text-ink">{isSignup ? "Create your Mnemos workspace" : "Welcome back"}</h1>
          <p className="mt-2 text-[13px] leading-6 text-ink-soft">
            {isSignup ? "Create an organization-scoped account and start working with your own operational data." : "Access your approved plants, assets, investigations, and evidence."}
          </p>
        </div>

        <form className="mt-5 grid gap-3" onSubmit={handleSubmit} noValidate>
          {isSignup ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Full name" error={errors.name || errors.full_name}>
                <input autoComplete="name" className={fieldClass("name")} value={values.name} onChange={(e) => update("name", e.target.value)} placeholder="Dhruv Gupta" />
              </Field>
              <Field label="Organization" error={errors.organization || errors.organisation_name}>
                <input autoComplete="organization" className={fieldClass("organization")} value={values.organization} onChange={(e) => update("organization", e.target.value)} placeholder="North Process Plant" />
              </Field>
            </div>
          ) : null}

          <Field label="Work email" error={errors.email}>
            <input autoComplete="email" type="email" className={fieldClass("email")} value={values.email} onChange={(e) => update("email", e.target.value)} placeholder="dhruv@plantops.com" />
          </Field>

          <div className={`grid gap-3 ${isSignup ? "sm:grid-cols-2" : ""}`}>
            <Field label="Password" error={errors.password}>
              <PasswordInput
                autoComplete={isSignup ? "new-password" : "current-password"}
                className={fieldClass("password")}
                value={values.password}
                onChange={(event) => update("password", event.target.value)}
                visible={showPassword}
                onToggle={() => setShowPassword((current) => !current)}
              />
            </Field>
            {isSignup ? (
              <Field label="Confirm password" error={errors.confirmPassword}>
                <PasswordInput
                  autoComplete="new-password"
                  className={fieldClass("confirmPassword")}
                  value={values.confirmPassword}
                  onChange={(event) => update("confirmPassword", event.target.value)}
                  visible={showConfirmPassword}
                  onToggle={() => setShowConfirmPassword((current) => !current)}
                />
              </Field>
            ) : null}
          </div>

          <button disabled={submitting} type="submit" className="mt-1 rounded-full bg-rail px-5 py-2.5 text-[12.5px] font-medium text-white transition hover:bg-rail-raised disabled:cursor-not-allowed disabled:opacity-60">
            {submitting ? "Please wait…" : isSignup ? "Create workspace" : "Sign in"}
          </button>
        </form>

        {(submitting || redirecting) ? (
          <div className="mt-4 flex items-center gap-3 rounded-2xl border border-line bg-paper-sunk/70 px-4 py-3.5" role="status" aria-live="polite">
            <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white shadow-sm">
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-strong/25 border-t-signal-blue" />
            </span>
            <div>
              <div className="text-[12.5px] font-semibold text-ink">
                {redirecting ? "Workspace ready" : isSignup ? "Creating your workspace" : "Signing you in"}
              </div>
              <div className="mt-0.5 text-[11.5px] text-ink-soft">
                {redirecting ? "Opening your dashboard…" : "Securing your session and preparing the workspace…"}
              </div>
            </div>
          </div>
        ) : null}

        {status ? (
          <div className={`mt-3 rounded-xl border px-3.5 py-2.5 text-[12px] leading-5 ${status.tone === "error" ? "border-signal-red-line bg-signal-red-pale text-signal-red" : "border-line bg-paper-sunk text-ink"}`} role="status">
            {status.message}
          </div>
        ) : null}
        <div className="mt-4 text-center text-[11.5px] text-ink-faint">Tokens are stored in HttpOnly cookies through the Next.js authentication boundary.</div>
      </div>
    </div>
  );
}

function PasswordInput({ autoComplete, className, value, onChange, visible, onToggle }) {
  return (
    <div className="relative">
      <input
        autoComplete={autoComplete}
        type={visible ? "text" : "password"}
        className={`${className} pr-11`}
        value={value}
        onChange={onChange}
        placeholder="••••••••••••"
      />
      <button
        type="button"
        onClick={onToggle}
        className="absolute right-2.5 top-1/2 mt-[3px] flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-ink-faint transition hover:bg-paper-alt hover:text-ink focus:outline-none focus:ring-2 focus:ring-signal-blue/30"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4" aria-hidden="true">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4" aria-hidden="true">
      <path d="m3 3 18 18" />
      <path d="M10.6 6.15A10.4 10.4 0 0 1 12 6c6 0 9.5 6 9.5 6a16.2 16.2 0 0 1-2.2 2.85" />
      <path d="M6.2 6.2C3.8 8 2.5 12 2.5 12s3.5 6 9.5 6a9.7 9.7 0 0 0 3.2-.53" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
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
