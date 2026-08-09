# Decision: Supersede The Four-Sprint WBC Chain With A Gated Corrective Epic

Date: 2026-07-10

## Decision

The existing four-sprint Workflow Boundary Contracts chain is superseded as an
execution plan by a six-milestone corrective chain. The initiative and its
North Star remain canonical; existing notes, research, `s1`-`s4` briefs, and
`m1`-`m10` source briefs remain preserved as historical evidence and checklist
material.

The replacement chain must not launch until Run Authority is fully landed on
`main` with a matching content-addressed completion manifest. A merged first
milestone, status summary, or textual claim of completion is insufficient.
Megaplan Maintenance remains independent and is not a launch condition.

All six corrective milestones use the `partnered-5` profile with
`vendor: codex` declared per milestone and at driver level. The
chain uses automatic milestone approval and clean-PR merge. The C1 mutation
gate is enforced by objective acceptance artifacts and validation; failure
aborts the chain and cannot be converted into a human approval prompt.

## Why

The goals are compatible, but the former sequence was stale and assigned WBC
greenfield work over contracts now owned or changed by the prerequisites:
transition authority, execution authority, repair request identity and custody,
watchdog findings, status semantics, independent verification, six-hour audit
evidence, and runtime JSON.

Current implementation also invalidates greenfield assumptions: a substantial
boundary contract/receipt/finding registry and `TransitionWriter` already exist;
declared artifact names do not consistently match current producers; receipt
emission is best-effort after lifecycle state is saved; and synthetic health
tests do not prove real-run compatibility. Run Authority has introduced its
kernel and shadow execution/runner/publication views, with enforcement and
consumer migration still to land. Megaplan Maintenance is actively changing the
repair and observation contracts WBC would otherwise mutate concurrently.

The decision incorporates the two completed resident reviews with request IDs
`workflow-boundary-contracts-review-1-20260710` and
`workflow-boundary-contracts-review-2-20260710`. One established the six-part
corrective shape from current implementation; the other established the
concurrency no-go and prerequisite sequencing from live chain/workspace and
overlap evidence.

## Consequences

- C1 is read-only reconciliation and the explicit gate before shared mutation.
- C2-C4 integrate with prerequisite-owned runtime contracts rather than replace
  them.
- C5 owns boundary profiles/templates and authority adapters, not transition
  mutation.
- C6 proves mandatory conformance for the declared supported native runtime
  after Megaplan compatibility is stable; opt-in applies only to workflows
  outside the initiative's declared runtime support boundary.
- Every milestone has acceptance evidence and fail-closed conditions;
  ambiguity in ownership or schema compatibility aborts with diagnostics.
- Cloud execution uses the initiative-local configuration and unique
  workspace/session/log and requires no `--allow-human-gates` override.
- The old four-sprint and ten detailed briefs are not executable chain inputs.

This decision supersedes their sequencing and ownership assumptions, not the
incident history, research, or still-valid acceptance criteria they contain.
