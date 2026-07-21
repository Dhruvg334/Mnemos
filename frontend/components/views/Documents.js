"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { D } from "@/lib/data";
import { byId, docTypeLabel } from "@/lib/helpers";
import { Card, StatusPill } from "../ui";

const ACCEPTED = {
  ".pdf": "application/pdf",
  ".txt": "text/plain",
  ".md": "text/markdown",
  ".csv": "text/csv",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};
const MAX_SIZE = 25 * 1024 * 1024;

function extension(name) { return name.slice(name.lastIndexOf(".")).toLowerCase(); }
function displaySize(bytes) { return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
async function sha256(file) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

function UploadPanel({ onUploaded }) {
  const inputRef = useRef(null);
  const [state, setState] = useState({ status: "idle", progress: 0, message: "" });

  async function upload(file) {
    const ext = extension(file.name);
    const mimeType = ACCEPTED[ext];
    if (!mimeType) return setState({ status: "error", progress: 0, message: "Unsupported file. Use PDF, TXT, Markdown, CSV, DOCX, or XLSX." });
    if (file.size > MAX_SIZE) return setState({ status: "error", progress: 0, message: `File exceeds the ${displaySize(MAX_SIZE)} client limit.` });
    try {
      setState({ status: "hashing", progress: 5, message: "Calculating checksum…" });
      const checksum = await sha256(file);
      const sessionResponse = await fetch("/api/documents/upload-session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: file.name, mime_type: mimeType, size_bytes: file.size, sha256: checksum, document_type: ext.slice(1).toUpperCase() }) });
      const sessionPayload = await sessionResponse.json().catch(() => ({}));
      if (!sessionResponse.ok) throw new Error(sessionPayload?.error?.message || "Upload session could not be created.");
      setState({ status: "uploading", progress: 25, message: "Uploading source file…" });
      const uploadResponse = await fetch(sessionPayload.data.upload_url, { method: "PUT", headers: sessionPayload.data.required_headers, body: file });
      if (!uploadResponse.ok) throw new Error("Object storage rejected the upload.");
      setState({ status: "processing", progress: 70, message: "Extracting and indexing readable evidence…" });
      const confirmResponse = await fetch(`/api/documents/${encodeURIComponent(sessionPayload.data.document_id)}/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ upload_session_id: sessionPayload.data.upload_session_id }) });
      const confirmPayload = await confirmResponse.json().catch(() => ({}));
      if (!confirmResponse.ok) throw new Error(confirmPayload?.error?.message || "Document processing failed.");
      const document = confirmPayload.data;
      if (document.status === "failed") throw new Error("Readable text could not be indexed. Image-only PDFs require OCR, which is not currently available.");
      setState({ status: "success", progress: 100, message: `${file.name} is indexed and available for retrieval.` });
      onUploaded(document);
    } catch (error) {
      setState({ status: "error", progress: 0, message: error instanceof Error ? error.message : "Upload failed." });
    }
  }

  return <Card className="p-4">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><div className="text-[13px] font-semibold text-ink">Upload operational evidence</div><div className="mt-1 text-[11.5px] text-ink-faint">PDF, TXT, Markdown, CSV, DOCX, XLSX · maximum {displaySize(MAX_SIZE)} · duplicate files are rejected by SHA-256.</div></div>
      <button type="button" onClick={() => inputRef.current?.click()} className="rounded-md bg-rail px-4 py-2 text-[12px] font-medium text-white hover:bg-black">Select file</button>
      <input ref={inputRef} className="hidden" type="file" accept={Object.keys(ACCEPTED).join(",")} onChange={(event) => event.target.files?.[0] && upload(event.target.files[0])} />
    </div>
    <button type="button" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const file = event.dataTransfer.files?.[0]; if (file) upload(file); }} onClick={() => inputRef.current?.click()} className="mt-3 flex min-h-24 w-full items-center justify-center rounded-lg border border-dashed border-strong bg-paper-alt px-4 text-center text-[12px] text-ink-soft hover:border-ink-faint">Drop one supported document here, or click to browse.</button>
    {state.status !== "idle" ? <div className={`mt-3 rounded-md border px-3 py-2 text-[11.5px] ${state.status === "error" ? "border-red-200 bg-red-50 text-red-700" : state.status === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-line bg-paper-alt text-ink-soft"}`}><div className="mb-1 h-1.5 overflow-hidden rounded-full bg-paper-sunk"><div className="h-full bg-rail transition-all" style={{ width: `${state.progress}%` }} /></div>{state.message}</div> : null}
  </Card>;
}

export default function Documents({ activeDocId, onOpenAsset }) {
  const [sessionUser, setSessionUser] = useState(undefined);
  const [documents, setDocuments] = useState([]);
  const [active, setActive] = useState(activeDocId || null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const response = await fetch("/api/documents", { cache: "no-store" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.error?.message || "Documents could not be loaded.");
    setDocuments(payload.data || []); setActive((current) => current || payload.data?.[0]?.id || null);
  }, []);
  useEffect(() => { fetch("/api/auth/session", { cache: "no-store" }).then(async (r) => r.ok ? r.json() : null).then((p) => { const user = p?.data || null; setSessionUser(user); if (user) load().catch((e) => setError(e.message)); }).catch(() => setSessionUser(null)); }, [load]);
  useEffect(() => { if (activeDocId) setActive(activeDocId); }, [activeDocId]);

  if (sessionUser === undefined) return <Card className="p-5 text-[12px] text-ink-faint">Loading document workspace…</Card>;
  if (!sessionUser) {
    const d = byId(D.docs, active || "doc_003"); const a = d ? byId(D.assets, d.asset) : null;
    return <div className="space-y-4"><div className="rounded-xl border border-line bg-paper-alt px-4 py-3 text-[12.5px] leading-relaxed text-ink"><strong>Synthetic demonstration evidence.</strong> Sign in to upload, process, and query real workspace documents.</div><div className="grid grid-cols-1 gap-4 lg:grid-cols-[340px_minmax(0,1fr)]"><Card className="p-0">{D.docs.map((doc) => <button key={doc.id} onClick={() => setActive(doc.id)} className={`block w-full border-b border-line px-4 py-3 text-left ${doc.id === d?.id ? "bg-paper-sunk" : "hover:bg-paper-alt"}`}><div className="text-[13px] font-medium text-ink">{doc.title}</div><div className="mt-1 text-[11px] text-ink-faint">{docTypeLabel(doc.type)} · {doc.date}</div></button>)}</Card><Card className="p-6"><h2 className="text-[20px] font-semibold text-ink">{d?.title}</h2>{a ? <button onClick={() => onOpenAsset(a.id)} className="mt-2 rounded bg-rail px-2 py-1 font-mono text-[11px] text-white">{a.tag}</button> : null}<div className="mt-5 whitespace-pre-line text-[13.5px] leading-7 text-ink">{d?.body}</div></Card></div></div>;
  }

  const selected = documents.find((doc) => doc.id === active);
  return <div className="space-y-4"><UploadPanel onUploaded={(doc) => { setDocuments((items) => [doc, ...items.filter((item) => item.id !== doc.id)]); setActive(doc.id); }} />{error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">{error}</div> : null}<div className="grid grid-cols-1 gap-4 lg:grid-cols-[340px_minmax(0,1fr)]"><Card className="max-h-[620px] overflow-y-auto p-0"><div className="border-b border-line px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Workspace documents</div>{documents.length ? documents.map((doc) => <button key={doc.id} onClick={() => setActive(doc.id)} className={`block w-full border-b border-line px-4 py-3 text-left ${doc.id === active ? "bg-paper-sunk" : "hover:bg-paper-alt"}`}><div className="text-[13px] font-medium text-ink">{doc.filename}</div><div className="mt-1 flex items-center justify-between text-[10.5px] text-ink-faint"><span>{doc.document_type} · {displaySize(doc.size_bytes)}</span><StatusPill tone={doc.status === "ready" ? "ok" : doc.status === "failed" ? "critical" : "warn"}>{doc.status}</StatusPill></div></button>) : <div className="px-4 py-8 text-center text-[12px] text-ink-faint">No documents have been uploaded to this site.</div>}</Card><Card className="min-h-[420px] p-6">{selected ? <><div className="text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">{selected.document_type} · {selected.id}</div><h2 className="mt-2 text-[20px] font-semibold text-ink">{selected.filename}</h2><div className="mt-3 flex flex-wrap gap-2 text-[11px] text-ink-faint"><span>{displaySize(selected.size_bytes)}</span><span>SHA-256 {selected.sha256.slice(0, 12)}…</span><StatusPill tone={selected.status === "ready" ? "ok" : selected.status === "failed" ? "critical" : "warn"}>{selected.status}</StatusPill></div><div className="mt-6 rounded-lg border border-line bg-paper-alt p-4 text-[12.5px] leading-relaxed text-ink-soft">The backend stores page, sheet, or section locators and bounded text chunks for retrieval. Source text is not mirrored into the browser document list. Query results expose only evidence excerpts permitted by the authenticated site scope.</div></> : <div className="flex min-h-[350px] items-center justify-center text-[12px] text-ink-faint">Select a document to inspect its ingestion status.</div>}</Card></div></div>;
}
