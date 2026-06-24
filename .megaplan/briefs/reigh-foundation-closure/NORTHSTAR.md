# North Star: Reigh Foundation Closure

## End State

The Reigh extension foundation is cleared for the next controlled Phase 4 extension-family sprint because its core contracts are public, typed, provider-backed, user-visible, and release-gated. The platform does not merely have milestone artifacts or readiness prose; it has executable evidence that future extension work can rely on stable proposal import, proposal acceptance, settings persistence, lifecycle/diagnostics readiness, and honest trust boundaries.

At the end of this epic:

- `ProposalRuntime` exposes proposal import as a public SDK/runtime contract, and edge proposal import depends on that typed contract rather than duck-typed concrete internals.
- The agent proposal path is proven vertically: mocked edge proposal response -> `useAgentSession` import -> production-mounted `ProposalPanel` -> user accept -> `TimelineOps.apply()`, with no timeline mutation before explicit acceptance.
- Extension runtime `settings.set()` writes through to provider-backed state on set, preserves safe fallback behavior, reports persistence failures, and remains coherent with manager-visible settings snapshots.
- Readiness is a release-quality gate: blocking contract rows have runnable evidence, readiness is wired into a normal quality/release command, and `docs/extensions/foundation-closure-assessment.md` says whether Phase 4 is cleared based on evidence.
- `docs/extensions/foundation-contract-ledger.md` is the persistent contract ledger for this foundation. It records each blocking contract, source brief, owner files, evidence command, current status, and any explicit waiver.

## Non-Negotiables

- Chain completion must use the Megaplan publication guard: a PR-backed milestone is not complete unless the published PR/merge diff contains semantic product work or a valid typed no-op waiver.
- No milestone may clear by documentation-only evidence when behavior is required.
- Every blocking contract needs a named test or release command that would fail if the contract regresses.
- Do not change the chain profile model selections. Preserve the existing `partnered-5`, Codex, robustness, and depth choices.
- Do not claim broad Phase 4 readiness unless the contract ledger has no unresolved blocking rows.
- Keep work scoped to closing the foundation gaps named in this epic; avoid opportunistic editor refactors.

## Explicit Non-Goals

- Marketplace, signing, sandboxing, permission broker, remote install, and published external SDK package are not part of this closure epic.
- Broad Phase 4 contribution-family implementation is not part of this closure epic.
- Cosmetic UX polish is not a substitute for contract closure.
- A green anchor/readiness document check is not sufficient unless it points to executable passing evidence.

## Allowed Temporary Bridges

- Pending-only proposal reload may remain the contract if it is explicitly documented, tested, and reflected in the ledger.
- LocalStorage compatibility may remain as fallback/migration support if provider-backed repository snapshots are canonical whenever a repository is available.
- Browser/Playwright validation may remain a named slow/manual gate only if the release-readiness artifact is explicit about when it must be run and why it is outside the default fast quality command.

## Drift Signals

- A milestone closes with only `.megaplan/**` changes while claiming implementation work.
- A readiness row says `cleared` but cites only a doc anchor or string-existence check.
- Proposal behavior is tested only through helpers/components and not through the edge-to-panel accept/apply vertical.
- Settings persistence tests pass only because state is flushed on dispose rather than written through on set.
- A future brief tries to start Phase 4 family work while any blocking contract ledger row is open.

