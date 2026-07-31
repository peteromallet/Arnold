# Native Workflow Platformization

**Status: prepared / not launched.**

This directory is the launch source for the seven-milestone follow-on epic that
turns the reusable-workflow Platformization ticket into an executable Megaplan
chain. Preparing or reading these files does not initialize or launch a plan.
No chain state or milestone plan should exist for this initiative yet.

## Predecessor and handoff

The epic may launch only after
`megaplan-chain-milestone-gates` is accepted with exact manifest-bound
`downstream-spec-readiness.json`, `completion-crosswalk-readiness.json`, and
`editable-runtime-readiness.json`, and after
`megaplan-native-parity-corrective` is accepted with its current
content-addressed chain completion manifest and its explicit
`platformization-handoff-manifest.json`. The handoff must bind the accepted
candidate inventory and coupling map, contract snapshots, source-to-runtime
golden adapters, diagnostic/DX corpus and numeric baselines, production CAS and
adapter provenance, governed producer/manifest evolution inputs, generic-import
proof and outgoing-seam disposition.
It must also bind the exact C1/C2 completion-kernel manifests, S2R's sole
kernel-enablement receipt, current content-addressed divergence-ledger hash,
completion schemas/serialization/decoder matrix, candidate-outcome registry,
proof corpus, false-done/`REVIEW` fixture, legacy completion-writer retirement,
and Custody's exact bounded-projection/57k benchmark receipt.
The Native completion proof map must list the handoff as a mandatory proof
artifact, and the validated completion manifest must bind its path and content
hash. The chain uses `chain_completed + require_manifest` plus explicit
artifact preconditions. S1's intake gate then requires each exact path once in
the validated manifest and verifies its current hash against the corresponding
proof row; `contains_text` or standalone existence is never handoff proof.
It must also prove `.pype` is the sole live authoring and packaged workflow
suffix; `.pypeline` may appear only as classified historical or pinned
pre-cutover identity and is not a supported Platformization input.
The handoff must attest the full one-workflow-per-file contract in
`docs/arnold/pype-authoring-contract.md`, not merely the suffix rename.

Platformization consumes those artifacts and the admitted M11/Native Run
Authority, Custody, WBC, effect, recovery, projection, worker and proof
substrate. Missing or incomplete evidence blocks launch and is repaired in the
owning predecessor; this epic does not create a local substitute.

## Relationship to `native-platform-followup`

The existing `.megaplan/initiatives/native-platform-followup/` chain is a
separate, historical production-hardening epic. It covered side-effect
reconciliation, credential brokerage, durable backends, shared packs, worker
supervision and production conformance around the earlier native composition
surface. It is not relaunched, replaced or treated as the source of this new
component standard.

`native-workflow-platformization` owns the later, narrower question: can
qualified steps and subworkflows be contracted, clean-installed, isolated,
recomposed and substituted across genuinely different product workflows after
Native Parity has made the Python topology authoritative? Where the completed
`native-platform-followup` substrate remains canonical, it is consumed through
the predecessor handoff. Any overlap is resolved by reuse and conformance—not
by duplicating stores, lifecycle semantics, effect machinery, worker ownership
or proof infrastructure.

## Artifact map

- `NORTHSTAR.md` — durable destination and non-negotiable boundaries.
- `decisions/PLATFORM_CONTRACT.md` — normative cross-milestone decisions and acceptance
  contract.
- `docs/arnold/workflow-execution-mode-dispositions.yaml` — sole machine
  registry for modes,
  dispositions, rule assignments, store/capability access, and logical
  isolation; prose views are derived/informative.
- `chain.yaml` — executable serial chain, exact predecessor-handoff assertion,
  S1–S5 intermediate gates, S6 final gate, and typed receipt-consuming
  transitions with post-transition verification for S2A, S4, and S6.
- `briefs/s1-component-standard-extraction-inventory.md` — candidate standard
  and executable contract corpus, including the exact Native completion
  candidate.
- `briefs/s2a-enforced-composition-resolution-package-surface.md` —
  product-neutral runtime, lifecycle, completion admission/binding/evaluation,
  attempted-finish/session-continuation lifecycle, and authority enforcement
  without another kernel enablement.
- `briefs/s2b-pype-authoring-format-toolchain.md` — product-neutral `.pype`
  compiler/linker, packaging, conservative digest, distribution identity,
  converter, transactional refactors, and Native's frozen response-directory
  step-authoring compiler, optionality projection and typed repair dispositions
  as one install-equivalent authoring core.
- `briefs/s3-developer-experience-tooling.md` — generic CLI/editor/navigation,
  format/lint/topology/preview/test, ownership-aware response-package editing,
  concise generated prompts, normalized parse/same-session repair and completion
  inspection/generated-view experience, author tasks, and benchmarks over the
  S2B core.
- `briefs/s4-isolated-extraction-recomposition.md` — first extraction,
  isolation and recomposition proof.
- `briefs/s5-adversarial-second-consumer-substitutability.md` — unrelated
  consumer, four-axis authoring-package, evolution and substitution challenge.
- `briefs/s6-certification-evolution-adoption.md` — stable certification,
  publication and completion proof.
- `scripts/validate_native_workflow_platform_stage_gate.py` plus per-milestone
  proof maps — S1 outputs consumed before and after every S1–S5 merge.
- `scripts/validate_native_workflow_platform_transition.py` plus the registered
  S2A/S4/S6 non-shell handlers — post-validation transitions and independent
  after-state verification; S1 defines the shared fixed contract and the owning
  milestone supplies its state change.
- `final-proof-map.json` and `completion-manifest.json` — S6 outputs; they are
  intentionally absent before execution.

Canonical context remains in:

- `docs/arnold/megaplan-native-representation-report.md`;
- `.megaplan/initiatives/megaplan-native-parity-corrective/` and its eventual
  Platformization handoff; and
- ticket
  `01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md`.

## Exact milestone order

1. `s1-component-standard-extraction-inventory`
2. `s2a-enforced-composition-resolution-package-surface`
3. `s2b-pype-authoring-core`
4. `s3-developer-experience-tooling`
5. `s4-isolated-extraction-recomposition`
6. `s5-adversarial-second-consumer-substitutability`
7. `s6-certification-evolution-adoption`

S1 freezes the generic candidate and proof corpus; S2A promotes the accepted
runtime and exact Native completion implementation in place; S2B productizes
the S4-blocking authoring/package/identity/refactor and completion-template
core plus Native's frozen response-directory step-authoring compiler; S3
completes the public developer experience, ownership-aware package editing,
normalized parse previews, targeted repair and non-authoritative completion
views; S4 extracts the first patterns and makes Megaplan consume
them without a duplicate completion writer; S5 challenges them with a
mechanically independent unrelated consumer whose authoring package has no
Markdown body, deeply nested records, a human-authorized gate and concurrent
attempts. Only S6 may certify a stable public standard or package.

Completion schemas and the persisted binding envelope are internally versioned
from Native C1/M1. Authoritative persisted-wire compatibility and decoder
enforcement begin at Native S2R's GO-0 enablement. Platform S6 decides the
stable public authoring/API promise after the unrelated consumer; it does not
retroactively create storage compatibility.

## Launch state

Preparation deliberately does **not** run `megaplan init`, `megaplan chain
start`, or `megaplan chain manifest`. It creates no plan, branch, PR, cloud
session, chain-state record, proof map or completion manifest. Until the
predecessor completion and handoff exist, verification should fail specifically
at those launch preconditions; that is the intended safe state.

Read-only status, when useful:

```bash
python -m arnold_pipelines.megaplan chain status \
  --spec .megaplan/initiatives/native-workflow-platformization/chain.yaml
```

After Native Parity completes, the handoff is present, and the initiative is
committed and clean, verify the launch contract:

```bash
python -m arnold_pipelines.megaplan chain verify \
  --spec .megaplan/initiatives/native-workflow-platformization/chain.yaml
```

Only after that command is fully green should an operator explicitly launch:

```bash
python -m arnold_pipelines.megaplan chain start \
  --spec .megaplan/initiatives/native-workflow-platformization/chain.yaml
```

## Ticket provenance

This epic promotes the open human-authored ticket
`01KY2DWSJG0B9YKAJRYA0107XE`, “Build a reusable native workflow-pattern
platform after Megaplan parity.” The ticket remains the issue/provenance record
and should remain open while the epic is only prepared. Epic completion—not
file preparation—must satisfy the ticket through the accepted, content-addressed
Platformization completion proof.
