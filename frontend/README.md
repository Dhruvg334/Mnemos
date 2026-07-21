# Mnemos frontend

The Mnemos frontend is a Next.js 15 App Router application for the public product experience, technical documentation, authentication entry, and the operational industrial-intelligence dashboard.

## What is included

### Public experience

- centered product landing page
- About page covering the product direction, design rationale, benefits, and team responsibilities
- unified Sign in / Create account panel with client-side field validation
- public navigation and footer
- redesigned Mnemos memory-lattice identity

### Technical documentation

The documentation is structured for both rapid evaluator review and deeper engineering inspection:

```text
/documentation
/documentation/architecture
/documentation/workflows
/documentation/agentic
/documentation/ingestion
/documentation/retrieval
/documentation/infrastructure
/documentation/governance
/documentation/deployment
```

It includes responsive SVG diagrams for:

- production topology
- agentic query execution
- document ingestion and provenance
- governed knowledge lifecycle

### Operational dashboard

The current dashboard includes:

- plant overview
- asset explorer
- asset passport
- RCA investigation workspace
- compliance matrix
- knowledge graph
- document library
- expert-knowledge review
- evidence drawer and citation navigation

The dashboard currently uses `lib/data.js` as a transitional demo adapter. The next integration phase replaces this data screen by screen with backend API calls.

## Technology

- Next.js 15 App Router
- React 19
- Tailwind CSS
- dependency-free CSS motion with `prefers-reduced-motion` support
- inline responsive SVG diagrams
- plain JavaScript

No external UI kit or runtime animation library is required.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

For production validation:

```bash
npm run build
npm start
```

## Route map

| Route | Purpose |
|---|---|
| `/` | Public product landing page |
| `/about` | Product direction, benefits, rationale, and team |
| `/signin` | Unified auth panel, Sign in mode |
| `/signup` | Unified auth panel, Create account mode |
| `/documentation` | Technical overview |
| `/documentation/*` | Engineering deep dives |
| `/dashboard` | Operational product dashboard |

## Structure

```text
frontend/
├── app/
│   ├── about/
│   ├── dashboard/
│   ├── documentation/
│   ├── signin/
│   ├── signup/
│   ├── globals.css
│   ├── layout.js
│   └── page.js
├── components/
│   ├── public/             # brand, navigation, docs, auth, diagrams
│   ├── views/              # dashboard screens
│   ├── Drawer.js
│   ├── Rail.js
│   ├── Shell.js
│   └── Topbar.js
├── lib/
│   ├── data.js             # transitional demonstration data
│   └── helpers.js
├── package.json
└── tailwind.config.js
```

## Frontend safety review

The current frontend code:

- does not use `dangerouslySetInnerHTML`
- does not use `eval` or dynamic function construction
- does not persist tokens in `localStorage` or `sessionStorage`
- does not inject third-party scripts
- emits baseline browser security headers through `next.config.mjs`
- uses internal Next.js links for navigation
- validates auth form inputs before submission
- uses semantic labels and visible keyboard focus states
- respects reduced-motion preferences

### Authentication integration requirement

The current auth panel is not yet connected to the backend. During integration:

- access tokens should remain short-lived
- refresh tokens should be handled through a protected server or HTTP-only cookie boundary rather than long-lived browser storage
- backend validation remains authoritative
- server error messages should be mapped to safe field and form states

### Dependency maintenance

Run dependency review before deployment:

```bash
npm audit
```

The repository currently remains on the existing Next.js 15 line for compatibility. Before public deployment, upgrade to an officially patched supported release and regenerate `package-lock.json` through the normal npm registry. Do not hand-edit lockfile integrity values.

## Integration roadmap

1. Add a typed API client or validated JavaScript contract layer.
2. Connect login, refresh, logout, and current-user flows.
3. Add protected routing and real site selection.
4. Replace static overview and asset data.
5. Integrate document upload and ingestion progress.
6. Integrate asynchronous query execution, citations, cancellation, and retry.
7. Connect RCA, compliance, expert-knowledge, and audit workflows.
8. Add component, integration, accessibility, and end-to-end tests.

## Authentication boundary

The frontend now uses Next.js route handlers as a browser-facing authentication boundary. Access and refresh tokens are stored in HttpOnly, SameSite=Lax cookies rather than browser storage. Configure:

```env
MNEMOS_API_URL=http://localhost:8000/api/v1
AUTH_REQUIRED=false
AUTH_REFRESH_COOKIE_SECONDS=604800
```

The dashboard is intentionally public as a read-only demonstration workspace. Authentication is required only for actions that modify private organisation data. New registrations are active immediately in the current public release; email verification is intentionally outside the current release scope.
