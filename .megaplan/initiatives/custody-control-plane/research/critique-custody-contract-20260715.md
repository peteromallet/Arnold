# Critique custody contract: production, clearance, finalization, and execution

## Evidence and scope

This is the curated implementation record for resident implementation run
`subagent-20260715-122715-f5ca5724`, requested by Discord source message
`1526927839633608714` (`msg_ee3ae73d5f34`) in resident conversation
`rconv_85a1c2bfd5f1`. The triggering read-only diagnosis was run
`subagent-20260715-121517-e803dd1b`; its resident completion message is
`msg_c01eac825f19`.

The canonical captured graph evidence remains in
`task-sizing-dependency-test-budget-investigation-20260715.md`: 35 tasks, 34
edges, one root, width one, and a critical path containing every task. This
record adds the previously missing cross-stage explanation and the implemented
contract. It does not copy resident transcripts or mutate the captured run.

## Root cause

The failure was a general evidence-custody defect, not primarily a model-quality
failure. A parallel critique worker could produce a valid top-level `flags`
array, including the oversized-task findings. The reducer retained only its
derived `checks` entry and returned `flags: []`. Check-to-flag synthesis later
covered some shapes, but it ran after the critique artifact was written and no
immutable receipt joined producer evidence to registry identity, revise
mutation, gate resolution, finalizer input, or the final graph. Gate could
therefore receive effectively clean input. Finalize then created a new graph
after gate, outside the earlier critique authority.

Adjacent susceptible paths were any model-to-handler normalization or scratch
promotion that could discard fields, any registry update that ignored unknown
or duplicate IDs, any gate consuming a projection without validating its
producer receipt, and any post-gate generator or mutation that was not rebound
to the evidence that authorized it.

## Implemented invariants

The code now enforces these owner-local invariants:

1. Every flagged check finding is materialized as exactly one top-level flag.
   Typed producer flags are preserved by the parallel reducer with their source
   lens. Category/severity aliases retain producer values while normalizing to
   the typed schema; unknown or lossy finding fields fail closed.
2. `critique_custody_vN.json` binds versioned raw/producer artifacts, the exact
   plan and critique hashes, expected lenses, stable finding and flag IDs, and
   zero-loss normalization counts. Missing, malformed, duplicate, ambiguous,
   tampered, or unmatched evidence blocks.
3. Gate validates that receipt before model dispatch and proves every receipt
   flag exists in the registry. A normalized-clean critique cannot reach gate.
4. Finalize creates `critique_clearance.json` by joining every production
   receipt to current registry state. A valid substantive finding clears only
   through a concrete revised-plan mutation plus verification, or an
   evidence-backed invalidation. Blocking findings cannot be accepted as a
   tradeoff. Partial mappings remain blocking.
5. Finalize receives the clearance as immutable input and must return an exact,
   typed finding-to-final-task coverage map. Partial, duplicate, empty, or
   unknown mappings block. The handler reruns DAG feasibility after all
   finalizer/baseline mutations and binds clearance plus coverage to the exact
   task-contract hash. Execute revalidates feasibility, coverage, and critique
   custody before approval or mutating preflight.
6. The captured 35-node linear graph, or an equivalent fixture, is rejected by
   deterministic `serial_graph_unjustified` admission. Editing or regenerating
   an admitted graph invalidates its binding and rejects execution.

Legacy finalized v1 artifacts remain readable. Every newly finalized v2 code
graph requires the new execution-time custody binding.

## Custody / Cluster Control Plane coverage

This implementation is a direct partial delivery of **M8A**: Megaplan owns the
semantic finding, plan mutation, DAG feasibility, and executor admission
policy. M8A already required post-finalize revalidation, stable feasibility
diagnostics, graph hashing, and execution rejection; it did not previously
specify the critique production/normalization/resolution receipt or the
finding-to-plan-mutation join added here.

**M8** covers universal runtime/boundary adoption and is where this receipt
shape should be registered if critique/gate/finalize become declared WBC
boundaries across alternate runtimes. It does not, by itself, define whether a
planning critique is substantively resolved. **M11** should add generated
cross-runtime conformance and bypass-retirement cases for these new artifacts.
**M6A** provides the eventual transactional WBC attempt/effect store but does
not replace this Megaplan-domain semantic contract. **M7** grants action
exclusivity, not finding resolution. **M9** may project custody status but must
not authorize clearance. **M10** retry/replay safety must preserve these exact
receipt and graph identities if a planning phase is replayed.

Therefore the active epic substantially anticipated the structural class, but
M8A lacked this exact contract and M8/M11 have not yet proved universal
adoption. This patch must not be reported as completion of those milestones or
as external runtime activation.
