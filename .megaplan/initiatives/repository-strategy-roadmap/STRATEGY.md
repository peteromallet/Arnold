---
schema_version: megaplan-strategy-v1
---

# Repository Strategy

## Mission

Arnold builds intelligent pipelines out of many coordinated models. Its first tool, Megaplan, is a planning and execution harness that makes LLM-driven software development systematically robust by decomposing work into independently checked phases, each running on the cheapest model that can do it well.

## Principles

- Structure makes LLMs robust — decompose, scope, and independently check every phase.
- Use the cheapest capable model per component; reserve premium models for adjudication and genuinely hard work.
- Typed Markdown is authoritative; generated JSON is a disposable projection.
- Strategy entries point to artifacts, never copy bodies or lifecycle state.

## Architecture Direction

- Pipeline phases are explicit stages with typed I/O contracts.
- Model routing is profile-driven and vendor-neutral at the agent-spec level.
- Run state is durable and recoverable; custody and audit trails are first-class.
- The strategy contract separates stable direction from the living roadmap.

### Native workflow program sequence

The authoritative rationale and ownership split live in
[`docs/arnold/completion-spec-sequencing-and-ownership.md`](../../../docs/arnold/completion-spec-sequencing-and-ownership.md).
The required native critical path is:

1. accept and manifest the post-M11 Custody release;
2. complete the one-sprint
   [`megaplan-chain-milestone-gates`](../megaplan-chain-milestone-gates/)
   bootstrap;
3. run
   [`megaplan-native-parity-corrective`](../megaplan-native-parity-corrective/)
   through its ordered `S1 -> S2F -> C1 -> C2 -> S2R -> S3A -> S3B -> S4
   -> S5A -> S5B -> S6 -> S7` chain; and
4. only then run
   [`native-workflow-platformization`](../native-workflow-platformization/)
   through `S1 -> S2A -> S2B -> S3 -> S4 -> S5 -> S6`.

The completion kernel is deliberately embedded as Native Parity C1/C2 after
S2F establishes canonical subject identity and before S2R makes durable
control primitives authoritative. The preserved
[`standardized-completion-specifications`](../standardized-completion-specifications/)
initiative is a normative requirement and traceability index only. It is
retired, non-launchable, and must never become a competing chain or authority.

The
[`critique-ledger`](../critique-ledger/)
initiative is a separate product integration line, not a fourth native
substrate owner. Run it only on the accepted post-M11 release and, operationally,
finish it before Native Parity begins; the latest safe boundary is before
Native S3A migrates the critique path. This ordering avoids concurrent
authority-changing cutovers while leaving the native completion-kernel
dependency graph unchanged.

The release prerequisite is executable, not narrative: Critique Ledger may
start only after ticket `01KYSBGRHM1S8R6RQ1DGZ7843Y` has an accepted
exact-revision release receipt and its deployed-canary blocker
`01KYVJ7A47TMH4BRGEV9JFTK10` is independently verified.

### Usable exits and gates

- **Post-M11 release:** the existing Megaplan product is usable on the
  content-addressed released runtime before any follow-on initiative starts.
- **Critique Ledger:** Megaplan remains usable throughout; exit requires the
  cumulative finding ledger, replay/accountability proof, coordinated cutover,
  and legacy writer/reader retirement to be accepted on that released base.
- **Milestone-gate bootstrap:** existing workflows remain usable; exit is a
  validated completion manifest plus content-addressed downstream-spec,
  completion-crosswalk, and editable-runtime readiness. It prepares but does
  not launch either downstream epic.
- **Native Parity:** each authority-changing milestone must consume an accepted
  predecessor receipt and pass its post-transition verifier. Epic exit leaves
  Megaplan usable on the canonical `.pype` topology with the completion kernel
  enabled, native execution/review/rework paths accepted, and competing legacy
  authority retired.
- **Native Workflow Platformization:** it starts only from the exact Native
  Parity handoff. Epic exit leaves Megaplan as a proven consumer of the shared
  workflow platform and permits a stable public completion/workflow API only
  after isolated recomposition and an independent second-consumer proof.

## Constraints

- Must work in dirty worktrees without cloud state for local validation.
- Ticket identity is a ULID; epic identity is a canonical initiative slug.
- The executable roadmap vocabulary is exactly `ticket` and `epic`.

## Non-Goals

- Replacing existing ticket/epic artifact storage with strategy entries.
- Making the generated projection JSON independently authoritative.
- Including every open ticket in the roadmap.

## Now

- [epic:repository-strategy-roadmap] Repository Strategy Roadmap
- [ticket:01KYSBGRHM1S8R6RQ1DGZ7843Y] Consolidate the post-M11 compatibility release before Native Parity
- [ticket:01KYVJ7A47TMH4BRGEV9JFTK10] Implement an honest deployed workflow canary runner
- [epic:critique-ledger] Critique Loop / Cumulative Finding Ledger Implementation Epic

## Next

- [epic:megaplan-chain-milestone-gates] Megaplan milestone conformance-gate bootstrap
- [epic:megaplan-native-parity-corrective] Megaplan Native Parity Corrective

## Later

- [ticket:01KTH21EC489596QWBC3419JC9] Add compact megaplan monitor command for plan and chain health
- [epic:native-workflow-platformization] Native Workflow Platformization
- [ticket:01KYVKPN6JHD19ZRM3WQF9XV8S] Provide backend-neutral WBC persistence and canonical deployed-evidence joins
- [ticket:01KYVQ6D5X008TT6RBNFCFCYZS] Make execute-authority recovery converge after a base refresh
