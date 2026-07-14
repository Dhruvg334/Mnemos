# Mnemos — asset intelligence platform

A Node.js (Next.js 14, App Router) + Tailwind CSS rebuild of the Mnemos
front-end prototype: plant-wide reliability KPIs, an asset explorer, an
evidence-grounded asset passport with a docked copilot panel, an RCA
investigation workspace, a compliance matrix, a knowledge graph, a document
library, and expert-knowledge review cards — all backed by the North Process
Plant demo dataset (P-117 recurring seal-leak scenario).

## Stack

- **Next.js 14** (App Router, React 18) — the Node.js server/build layer
- **Tailwind CSS** — utility-first styling, with a small custom design-token
  palette (`tailwind.config.js`) instead of generic defaults
- Plain JavaScript, no TypeScript, no external UI kit — every screen is a
  hand-built component

## Run it

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

For a production build:

```bash
npm run build
npm start
```

## Project layout

```
app/                 Next.js App Router entry (layout, page, global styles)
components/
  Shell.js           Owns navigation + drawer state, mounts the current view
  Rail.js            Left navigation rail
  Topbar.js           Top bar: breadcrumb, scope pills, search, user chip
  Drawer.js           Right-hand source-document drawer (opened from any ⌐cite chip)
  ui.js               Shared primitives: badges, cite chips, KPI cards, tables bits
  icons.js            Inline SVG icon set
  views/              One file per screen (Overview, Assets, Passport, Investigation,
                       Compliance, Graph, Documents, Expert)
lib/
  data.js             The full demo dataset (assets, failures, work orders, docs, RCA, graph…)
  helpers.js          Small formatting/lookup helpers
```

## Notes

- This is a front-end-only prototype — `lib/data.js` stands in for the API
  contracts the real product would call.
- Every cited claim (`⌐doc_00x`) opens the source drawer with the exact
  document text it was drawn from, carried through every screen as the
  evidence-traceability motif.
