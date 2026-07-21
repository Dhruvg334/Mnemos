# Frontend Architecture

## Runtime model

The frontend is a Next.js 15 App Router application. Public product and documentation pages are statically generated where possible. Authentication proxy routes execute on the server and keep backend base URLs and refresh-token handling out of client components.

## Application shell

The operational workspace is composed of:

- `Rail` for domain navigation and contextual counts;
- `Topbar` for breadcrumbs, search, notifications, and session state;
- `Shell` for view selection, shared spacing, evidence-drawer coordination, and scroll restoration;
- `Drawer` for source evidence and document context;
- view modules under `components/views/` for domain-specific workspaces.

The shell owns the consistent dashboard content boundary. Individual views own their internal grids and cards but must not introduce viewport-wide padding that conflicts with the shell.

## Public and authenticated boundaries

The dashboard can render a curated synthetic dataset without authentication. This mode is intentionally read-only. It does not create an anonymous backend principal and does not grant access to private workspace APIs.

Authenticated sessions are required for actions that mutate organisation data, including uploads, deletions, account changes, invitations, approvals, retries, and governed operational actions. Frontend modals communicate this boundary; backend dependencies enforce it.

## Data adapter

`frontend/lib/data.js` is the current demonstration adapter. It provides stable synthetic assets, documents, findings, timelines, graph relationships, and query results. Live workspace integration should replace this adapter by domain surface rather than mixing synthetic and private records in the same object.

A live-data view should:

1. call the Next.js server proxy rather than infrastructure directly;
2. preserve loading, empty, partial, and error states;
3. distinguish unavailable evidence from an empty result;
4. retain source identifiers for evidence drawer navigation;
5. keep mutation controls behind authenticated session checks.

## Layout system

- The shell provides a centred content width with responsive horizontal padding.
- `dashboard-page` establishes a zero-overflow content boundary.
- Cards and tables must remain `min-width: 0` inside grid columns.
- Multi-column layouts collapse before content becomes cramped.
- Fixed-size diagrams may use internal view boxes, but their rendered SVG must scale to the available container.

## Knowledge graph view

The graph uses a stable SVG view box and precomputed demonstration coordinates. The rendered canvas scales to its container rather than imposing a fixed minimum width. Node selection supports pointer and keyboard interaction. Detail and legend cards move below the graph on narrower screens and into a side column on wide screens.

For live graph data, the renderer should add deterministic layout or a bounded layout worker, enforce node/edge limits, and preserve evidence provenance for every displayed relationship.

## Accessibility expectations

- Interactive SVG nodes require keyboard activation and accessible labels.
- Focus indicators must remain visible.
- Status must not rely on colour alone.
- Motion respects `prefers-reduced-motion`.
- Dialogs and destructive-action gates require clear outcomes and safe defaults.

## Production validation

```bash
cd frontend
npm ci
npm run build
npm audit --omit=dev
```

A release is not complete when development mode renders successfully; the production build must generate all routes without static-generation, type, or bundle errors.
