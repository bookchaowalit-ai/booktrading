# BookFinance (booktrading) — Interview Case Study Supplement

*Tier A Interview Flagship in the
[Portfolio Interview Readiness Audit](../../../../../../docs/systems/interview-readiness-audit.md)
(solo-empire workspace — not part of this repo). This file is deliberately
short: [`README.md`](./README.md) is already a genuinely excellent product
document (architecture diagram, feature list, live operating status,
testing instructions, monitoring) — rare in this portfolio. Duplicating it
here would be noise. This file covers exactly what the README doesn't:
the interview-specific angle and what this pass actually found.*

## The one-line pitch

An AI-assisted crypto/prediction-market trading system that defaults to
**observe-only** and treats "should we let the bot trade real money" as a
gated question with evidence, not a toggle — most portfolio trading bots
skip straight to "look, it trades," this one's core feature is *proving it
shouldn't yet*.

## Why this is the strongest technical flagship in the portfolio

Verified, not asserted:
- **Real tests, and they pass.** 36 frontend tests (Vitest) across API
  service logic, error boundaries, a system-health smoke test, and a
  `/api/command-center` **contract test** — the frontend asserting the
  shape of its own backend contract is a real engineering habit, not
  boilerplate. Plus Python (`pytest`) and Go (`go test`) suites per the
  README, covering kill-switch logic and safety filters specifically.
- **A live, honest operating state in the README itself** — not "here's
  what it can do" but "here is the actual current drawdown number, and
  here is why the bot is currently halted." That's the same honesty
  principle applied to a system's *runtime state*, not just its UI copy.
- **Multi-language backend done for real reasons**: Go for the
  HTTP/WebSocket/gRPC server (performance, concurrency), Python for the
  strategy/prediction layer (the ML/data-science ecosystem), not
  polyglot-for-its-own-sake.
- **A second deliberate design system** (`DESIGN.md` — "The Pocket App":
  no-scroll, touch-first, 44px targets, safe-area-aware) distinct in both
  content and reasoning from `booknbook`'s "Midnight Stage" — evidence of
  designing *for the product*, not reusing one template everywhere.

## What this pass actually did

Frontend-only verification (the full stack needs Postgres/TimescaleDB,
Redis, and exchange credentials to run — out of scope without live
infrastructure to test against):

- `tsc --noEmit`, `vitest run` (36/36 passing), `next build` (30+ dashboard
  routes across en/th) — all verified clean.
- **Found and fixed a real rules-of-hooks violation** in
  `dashboard/evidence/page.tsx`: `useMemo` was called *after* an early
  `if (isLoading) return (...)`, meaning the component called a different
  number of hooks depending on loading state — the kind of bug that risks
  a "Rendered more hooks than during the previous render" crash exactly on
  the loading → loaded transition, i.e. every time the page actually
  finishes loading. Moved the hook (and its `gates` dependency) above the
  early return. This is the Evidence page specifically — one of the "Core
  5 observe-only" pages the README names as the primary trust surface —
  so this wasn't a cosmetic fix.
- Added the missing `eslint.config` (same gap as `booknbook` and
  `localcrm-frontend` — `next lint` had never been run non-interactively
  before) and fixed the 4 real errors it surfaced (`react/no-unescaped-entities`
  in `LoginModal.tsx`, `PnLDashboard.tsx`, `market-intel/page.tsx`).
  ~15 non-blocking warnings remain (missing `useEffect`/`useCallback`
  deps, `<img>` vs. `next/image`) — not fixed in this pass, same category
  as `localcrm-frontend`'s.

## What I'd say if asked "what would you improve"

The frontend has zero visibility into whether the rules-of-hooks class of
bug exists elsewhere — `eslint-plugin-react-hooks` was already a
dependency, just never run in CI against `next lint`'s strict mode before
this pass. Wiring `npm run lint` into the CI pipeline (the README documents
a CI/CD pipeline already, but doesn't mention lint as a gate) would have
caught this automatically instead of requiring a manual audit.

## Status

Interview case-study supplement + one real bug fixed: 2026-08-05. Design
system, backend, and the excellent existing README were not touched.
