# Native Build Forward — launch and durability root map

Status: canonical implementation handoff for this initiative. It is a compact
crosswalk, not a second ledger, plan, review packet, or progress signal.

## Authority and continuation boundary

The accepted root names and invariants below are taken from the operator's
lossless forensic synthesis at
`.otto/runs/nbf-launch-forensics-20260903/NBF-LAUNCH-ROOT-CAUSE-AND-REMEDIATION.md`.
That package remains immutable evidence; this handoff is the executable
initiative crosswalk. The source of truth for order is `../chain.yaml` and the
source of truth for durable destination is `../NORTHSTAR.md`.

The resident continuation has a completed prefix of exactly
`p0-mrc-intake-crosswalk → p1-custody-m11-admission →
p2-milestone-gate-bootstrap → native-s1-baseline → native-s2f-pype-format →
native-c1-completion-contract`. Its next position is `native-c2-completion-evaluation`.
This document does not copy, reset, or mint chain state. A resume must adopt
that prefix through the typed current-attempt restart/recovery transaction:
preserve the six-prefix under CAS, retire the progressed attempt once, and
create the continuation identity. Ordinary reconcile and `target-rebind` are
not adoption for progressed C2; `target-rebind` is pre-execute-only and C2 has
no `milestone.branch`. Any ordinary source/runtime transfer remains
quarantine-only until separately authorized.

Bucket A is the minimum safe prerequisite for the first real owner/provider/
fixer dispatch. Bucket B may begin after a real runner exists, but is required
for durable-running promotion and final Native proof. A root can have an A
slice and a B hardening slice; the table preserves one root identity without
creating micro-milestones.

For R14–R19, the Bucket A work is a conditional closure or not-applicable
receipt against the exact preserved remote chain state, not a new implementation
slice: capture the chain-state, marker/manifest, journal/hold/sequence, source,
and runtime identities and record why each recovery condition is closed or not
applicable. Any condition found applicable must be closed through its supported
operation before dispatch. R17 is unequivocally Bucket A: fresh liveness
authority must be reread at the final admission lock because the historical
marker was mistaken for live authority in the supported fresh launch.

## Accepted root/invariant crosswalk

| Root | Accepted invariant | Bucket A / Bucket B ownership in this chain | Proof home |
|---|---|---|---|
| R01 | Finalized/progressed paused attempts retire once, preserve prefix/custody, and expose one replayable terminal receipt. | A: current C2 continuation transaction; B: crash/replay completion. | C2; S2R |
| R02 | Legacy archives are promoted only from exact immutable bytes/layout/binding; otherwise typed refusal. | A only when the paused attempt uses legacy custody; B: bounded compatibility migration. | C2; S2R |
| R03A | One semantic runtime identity translates consistently across binding, marker, launch, rollback, migration, child, and recovery. | A: launch identity; B: remove duplicate serializers/readers. | C2; S2R; Platform S2A |
| R03B | A successful bound CAS returns and installs its committed revision; stale writers lose without clobber. | A: mandatory before any resumed write. | C2; S2R |
| R04 | One selected immutable source has complete Git objects and tracked launch assets at the destination. | A: custody/object/package admission. | C2 |
| R05 | Route is launch identity; continuation profile is closed and isolated without mutating legacy defaults or broker state. | A: exact route/environment parity. | C2 |
| R06A | Structured remote Git intent reaches every direct/compound probe; local/file clones stay local and output is sanitized. | A: authenticated source and runtime probes. | C2 |
| R06B | WBC starts before checkout, terminalizes every started attempt, and redacts before persistence; it is evidence, not authority. | A: pre-dispatch evidence boundary; B: complete terminal/recovery coverage. | C2; S6 |
| R06C | Provider construction installs the canonical deny-capable adapter; action-off dominates route and dispatch before transport/fence work. | A: provider/action-off parity. | C2; S5B |
| R07 | One generated launch boundary owns session/Git/runtime setup and propagates nonzero status; no child/sentinel starts on failure. | A: every effect-capable entrypoint. | C2 |
| R08 | Runtime creation/resume is bound to the reviewed wrapper, interpreter, import root, and dependency-generation provenance. | A: source-bound bootstrap. | C2 |
| R09 | Closed-route admission proves broker-backed model capability; raw key presence is not capability. | A: capability preflight. | C2 |
| R10 | Per-slug runtime authority classifies foreign/stale/partial pointers without overwrite and gives one idempotent outcome. | A: pointer/origin compatibility. | C2 |
| R11 | Protected reviewed bytes are admitted before writes; canonicalization uses a separate copy or refuses. | A: zero-write source admission. | C2 |
| R12 | Compound runtime probe emits exactly one parseable binding JSON on stdout; diagnostics stay separate. | A: structured runtime receipt. | C2 |
| R13 | Tracked-asset admission precedes reconciliation; reconciliation is explicit and precommitted, never implicit in validation. | A: precondition ordering. | C2 |
| R14 | Recovery CAS permits only the operation's enumerated journal delta, not a broad ledger-directory exemption. | A: conditional no-pending-owned-delta closure receipt; B: recovery/replay hardening. | C2; S2R |
| R15 | Held operations reconcile exact receipt kind/content/digest; path existence never implies an effect. | A: conditional no-held-effect closure receipt; B: crash/hold/retry hardening. | C2; S2R |
| R16 | Reviewed SHA/object provenance is verified in the authoritative source object DB before ancestry comparison. | A: conditional no-recovery-ancestry receipt; B: recovery custody hardening. | C2; S2R |
| R17 | Historical marker/manifest provenance is not occupancy; live authority requires fresh lease/fence/PID/provider/fixer evidence. | A: mandatory fresh preserved-state liveness receipt; B: durable autonomy/generalization. | C2; S6; Platform S2A |
| R18 | One allocator owns monotonic journal sequence; N/N+1 migration is exact, immutable, replayable, and no-effect when quarantined. | A: conditional no-pending-migration/sequence receipt; B: migration/sequence hardening. | C2; S2R |
| R19 | Failed workspace A, engine/runtime B, and reviewed descendant C remain distinct; A→B and B→C transitions are separately bound. | A: conditional preserved-topology receipt; B: recovery topology hardening. | C2; S2R |
| R20 | Resident source/package/lock/interpreter/CLI/wrapper/client/profile/capability/capacity form one attested closure. | A: minimum toolchain closure; B: generalize proven closure. | C2; Platform S2A |

## Operating rules

- The C2 brief is the only launch-critical intake for Bucket A. Do not create a
  bureaucracy epic, a parallel continuation chain, or a second root ledger.
- C2 records the exact preserved-state closure/not-applicable receipts for
  R14–R19 before dispatch; R17's fresh liveness receipt is mandatory, not
  optional. These receipts do not claim the later generic hardening complete.
- S2R owns Bucket B's durable primitives and recovery semantics; S6 owns
  source-authoritative control, liveness, and event-driven supervision;
  Platform S2A generalizes only patterns proven by Native evidence.
- Initial dispatch is not durable-running. Promotion requires successful real
  owner/provider/fixer dispatch, an active supervisor, observed milestone
  progress, restart/replay/recovery evidence, and no manual state surgery.
- Focused tests belong to the milestone making the change. Each milestone uses
  its configured Megaplan robustness and review behavior. There are no
  mandatory Megado per-batch Luna reviews, premium reviews, cumulative review
  packets, duplicate hashes, or seals-as-progress.
- The bounded planning set is this North Star, one chain spec, one brief per
  milestone, and generated plan/review/receipt evidence. Historical forensic
  artifacts remain evidence and are never rewritten as completion proof.
