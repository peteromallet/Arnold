# Alternative Oracle Answer 3 — sequencing adjudication

Date: 2026-07-21

Scope: Answer 3 (`F1`–`F12`) in
`/Users/peteromalley/Downloads/04_ORACLE_ANSWERS.md`, adjudicated against the
current eight-milestone Native Parity chain, active briefs, corrective plan,
representation report, and five-sprint Platformization ticket. No
authoritative asset was edited during this review.

## Decisive verdict

This Oracle reviewed an older packet than the current authoritative assets.
That is visible from the findings themselves: it treats S3 as one overloaded
milestone, says the Native-to-Platformization handoff has no producer, and
places exclusive resume selection after the first human cut. The current chain
has already split S3 into S3A/S3B, S3A owns the execution-plane resume binding,
and S7 emits a content-addressed Platformization handoff.

The response is nevertheless useful. Four findings remain clearly actionable,
three deserve narrower clarifications, four are already absorbed, and one is a
mixed workload judgment that needs code-level sizing before it can justify a
schedule change.

The prior Oracle from the thread is the better primary answer for executing the
real plan: it found and coherently resolved the main sequencing failures that
produced the current eight-milestone shape. This alternative Oracle is the
better complementary answer for subtle cross-version and cross-stage contract
questions. Its strongest novel contributions are manifest-schema evolution,
candidate-versus-stable standard status, continuity of the root-arbitration
actor/identity, and inheritance of the Native DX corpus.

No ninth Native sprint or sixth Platformization sprint follows from this answer
alone. The remaining findings fit S1 contracts/probes, existing per-milestone
receipts, and Platformization S1/S5 status language. S2 should be sized against
the code before deciding whether to split it; moving safety-critical LLM replay
machinery into the first product migration is not a safe shortcut.

## Finding-by-finding classification

| Finding | Current classification | Adjudication |
| --- | --- | --- |
| F1 — WBC producer-registry mutability | **Still novel; add an S1 capability clarification** | Current S1 probes external writer registration and pins exact-version WBC registries, but does not explicitly prove that producer entries are versioned mutable data under admitted decisions while the registry contract/schema digest remains pinned. Add a live probe that registers, versions, queries, and rejects an unauthorized producer without invalidating the admission lock. |
| F2 — comparison authority class missing from M11 | **Already absorbed** | Current S3A permits either storage-enforced `authority_class=comparison` **or** an immutable isolated artifact namespace with separate credentials and no RA grant, Custody/effect client, admitted writer, resume, or promotion path. Therefore an M11 authority-class dimension is no longer an unconditional prerequisite. S1 wording could mirror the same two-form rule for consistency, but the sequencing blocker is gone. |
| F3 — union-of-writers versus “authoritative and unfenced” | **Valid wording gap; proposed remedy needs correction** | The current plan still says a failed GO-1A leaves the old producer “authoritative and unfenced,” while also requiring every live writer behind the shared validator. Clarify that “unfenced” means **not hard-disabled as a producer**, never outside admission fencing. On failed cutover the old writer remains the one active admitted consumer behind the validator and the candidate remains non-authoritative. On successful cutover the old writer becomes registered-but-inactive/read-only. The Oracle's blanket suggestion that the old writer “may read, never consume” is wrong for a failed cutover, because the old writer must remain the active producer. |
| F4 — canonical execution plane versus primitive base | **Mostly absorbed; optional code-ownership clarification** | The current `Canonical machinery boundary` already declares `.pypeline -> DSL/manifest runtime` canonical and `Pipeline.native_program` a downstream compatibility consumer. S1's no-duplication map should record which partial `arnold/pipeline/native/*` implementation is ported, reused below the canonical lowerer, or quarantined, but the architecture no longer leaves the canonical plane undecided. |
| F5 — manifest schema evolution | **Genuine novel gap; update the plan** | The plan pins program/manifest digests and rejects stale workers, but does not assign versioning and compatibility for new manifest fields required by named exits, reconfiguration, model routing, and dynamic fanout. S1 should freeze a manifest-schema/version and canonical-hash evolution contract; S2 should implement it. Readers must reject unsupported schema versions before authority, in-flight runs must remain pinned to a compatible reader/artifact, and schema/hash-algorithm migration must be explicit rather than silently changing program identity. |
| F6 — S3 human reentry precedes cross-host proof | **Stale/absorbed; do not weaken current gate** | S3A now owns the digest-bound execution-plane selector and requires cross-host clarification resume through it before GO-1A closes. The old finding correctly motivated moving the selector earlier, but the suggested fallback to single-host proof is now weaker than the current safety contract and should not be adopted. |
| F7 — S2 scope and unproved agentic consumer | **Mixed** | The old S3 overload is resolved by S3A/S3B. S2 remains broad, but the packet alone does not prove it is structurally impossible; use a code-level estimate before adding/splitting a sprint. Do not move generic LLM/tool replay, budgets, and effect safety after GO-0 merely to reduce S2, because that makes the first product cutover the first real safety proof. The agentic subfinding is valid: S1 should identify the concrete current critique phase whose model-selected variable tool-call episode requires the primitive. If no such current phase exists, keep the protocol experimental/Stage 2 rather than manufacturing a Stage 1 parity consumer. |
| F8 — terminal-arbitration actor changes during Platformization | **Valid cross-stage clarification** | Freeze the role now: Megaplan source owns the closed arbitration **policy and participants**; a generic root-terminal acceptance boundary owns the CAS/admission actor from Stage 1 onward. Platformization may package that boundary as the root-host adapter without moving semantic occurrence, accepted-decision identity, or trace actor. Do not solve this by normalizing away the actor. Add the role/identity to the S1 semantic matrix and handoff manifest. |
| F9 — Platformization handoff has no producer | **Already absorbed** | Current Native S1 assigns extraction disposition per row; S7 emits the content-addressed handoff manifest; the final gate consumes it. No new work item is needed beyond maintaining those receipts. |
| F10 — two independently frozen DX corpora | **Genuine novel gap; update the ticket** | Platformization S1 should consume Native Parity's frozen corpus, benchmark environment, diagnostic contracts, and thresholds as its baseline, then extend them with component/recomposition tasks. A deliberate versioned successor may change the environment or thresholds, but an independent re-freeze must not erase comparability. S5 publishes results against the inherited/extended corpus. |
| F11 — restore re-exercise unassigned | **Mostly absorbed; clarify evidence timing** | Current S1 defines a durable-record ownership/restore matrix and S7 rejects every Native record lacking rollback-resistant ownership or its own restore-then-replay proof. Strengthen sequencing by saying each milestone that introduces a loop ledger, consumption join, comparison registry, or proof registry emits its restore receipt at introduction; S7 composes and replays those receipts rather than discovering ownership only at the end. This is a receipt-timing clarification, not a new sprint. |
| F12 — S1 “freezes” the platform standard before the adversarial second consumer | **Genuine and important; update ticket status language** | S1 should publish a content-addressed **candidate/experimental** Component Descriptor, lifecycle, composition, trace, and LLM contract. S2/S3 implement and extract against that candidate under explicit change control. S4 is allowed to falsify/revise it. Only S5 certification may mark the applicable standard/profile and components `stable`. The artifacts and sprint order do not move; only premature stability is removed. |

## Recommended bounded amendments

### Native Parity S1/S2

1. Add a producer-registry mutability/versioning capability probe (`F1`).
2. Add manifest schema, reader/writer compatibility, canonical hash-algorithm,
   and in-flight pin/migration rules (`F5`).
3. Replace “authoritative and unfenced” with unambiguous active-writer language:
   active but validator-fenced on failed cutover; registered inactive after a
   successful cut (`F3`).
4. Record canonical primitive code ownership/port/quarantine disposition in the
   no-duplication map (`F4`, low-cost hardening).
5. Require S1 to cite the concrete product agentic consumer or classify the
   primitive experimental (`F7`).
6. Record a stable `root_terminal_arbiter` role/occurrence in the semantic
   matrix so Stage 2 packaging does not change authority identity (`F8`).
7. Require restore evidence in the milestone that introduces each Native
   durable record, with S7 as composed replay (`F11`).

### Platformization ticket

1. Change S1's “freeze” to a content-addressed experimental/candidate standard;
   promote to stable only in S5 after S4's adversarial second consumer (`F12`).
2. State that Platformization consumes and extends Native Parity's DX corpus
   and benchmark baseline rather than independently resetting it (`F10`).

### No schedule change yet

Keep the current eight Native milestones and five Platformization sprints.
Before splitting S2, perform a source-level estimate of the missing generic
compiler/runtime work, with particular attention to manifest evolution,
dynamic fanout, checkpoints/reentry, and LLM/effect replay. If that estimate
shows the implementation plus GO-0 fault matrix cannot fit a two-week box,
split S2 along a real executable boundary; do not defer safety primitives into
S3A by default.

## Comparative quality: alternative versus prior Oracle

### Where the prior Oracle is better

- It was more current and operationally coherent.
- It found the resume-selector, seam-bridge, writer-adapter, M11 capability,
  S3 workload, restore, and handoff issues as one executable sequence.
- Its advice produced the correct major structural change: S3A/S3B and eight
  milestones.
- Its recommendations better respected the binary cutover gates and did not
  suggest weakening cross-host proof or making product migration the first LLM
  safety integration point.

### Where this alternative Oracle is better

- It more aggressively follows versioned artifacts through time, surfacing the
  missing manifest-schema evolution contract (`F5`).
- It spots a real platform-governance contradiction: calling the standard
  frozen before the adversarial second consumer exists (`F12`).
- It sees cross-stage identity continuity in root terminal arbitration (`F8`),
  not merely local Stage 1 correctness.
- It catches benchmark/corpus lineage (`F10`) and producer-registry mutability
  (`F1`), both easy to miss in a feature-oriented plan.

### Where this alternative overreaches

- “Not executable as sequenced” is too absolute against the current assets;
  several stated blockers have already been removed.
- F2 assumes comparison must inhabit M11 despite the current isolated-artifact
  option.
- F3's proposed read-only old writer is incompatible with a failed cutover
  where the old producer remains active.
- F6 proposes weakening proof that the current S3A deliberately moved earlier.
- F7's move of LLM runtime safety into S3A optimizes sprint shape at the cost of
  GO-0's purpose.

## Overall judgment

Use the prior Oracle as the sequencing baseline and this alternative as a
residual contract review. The alternative does not overturn the current plan,
but it should cause bounded amendments for F1, F3, F5, F8, F10, F11, and F12,
plus an evidence check for F7's claimed agentic consumer. The most consequential
two are F5 and F12: without manifest evolution, in-flight execution can become
version-ambiguous; without candidate-versus-stable status, the platform claims
standardization before the second consumer has had a chance to falsify it.
