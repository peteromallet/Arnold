# M5a — Node library + Behavioral Identity Manifest (R6)

**Epic:** Pipeline Unification (`.megaplan/briefs/pipeline-unification-EPIC.md`). Authoritative sequencing:
`.megaplan/briefs/validation/sequencing/PROGRAM.md` §201–214 (M5a entry) + the critical-path/strangler/open-risks
context. Organ specs: `.megaplan/briefs/validation/committed-uu/SYNTHESIS.md` (node library §112–148 of EPIC;
R6 Manifest §297–305, §379–381, §485). Open questions resolved from
`.megaplan/briefs/validation/human-blockers/REGISTER.md` §M5a (line 108).
**Tier/robustness:** premium · thorough/high.
**Delivers (PROGRAM §201–214):** (1) formalize `patterns` as the node-library composition vocabulary on
M2's typed Ports (NOT `GateRecommendation`), composing the M2 primitives + M3's loop-control node; (2)
stability tiers `stable|provisional|internal` + reserve `arnold_api_version`; (3) `escalate`/deadlock as
one node; (4) the **Behavioral Identity Manifest (R6)** — content-hash the behavioral closure, on which
M3's resume policy keys (pin/refuse/migrate-via-codemod).
**Depends on:** M2 (typed Ports + Contract-Ledger binder + `StateDelta` + `select`/`Reduce[T]`; the
4-verdict enum already evicted from `JoinFn`/SDK modules under the ZERO-`GateRecommendation` grep gate),
M3 (the realized graph the Manifest hashes; loop-control-as-a-node for the `iterate_until` rewrite; resume
keys on the Manifest), M4 (nodes call `emit`/`dispatch` — the service base M5a fans out from).
**Parallel:** with M5b ∥ M5-eval off the M4 service base (PROGRAM §348–359). **Do not start before M2's
ZERO-`GateRecommendation` grep gate is green** (partial conversion is worse than none — EPIC §265).
**Grounded:** 2026-05-29 against current main.

---

## Outcome

`patterns` becomes the **public composition vocabulary** ("the node library") — a documented surface of
named composition functions, each (a) **built on M2's typed Ports**, never on `GateRecommendation`;
(b) composing the M2 primitives (produce/judge/gate/revise/fan_out/reduce/select) + M3's loop-control
node; (c) declaring the Ports it **consumes/produces** so M1's `pipelines check` can statically prove a
composition is wired; (d) tagged with a **stability tier** (`stable|provisional|internal`) read from a
lightweight checker-readable registry; and (e) covered by a reserved `arnold_api_version`. `escalate`/
deadlock lands as one node. In parallel, the **Behavioral Identity Manifest (R6)** ships: a function that
content-hashes the behavioral closure of a realized graph (topology + Step-code hashes + resolved prompt
*bodies* + routing-taken + Port set + ABI version + resolved dep-closure), which M3's resume policy keys
on. After M5a a builder reads the node library to compose a pipeline; planning's binding (prompts/labels)
is touched only where the re-type forces it. **Additive — nothing is retired.**

---

## Scope (file:line)

Today `megaplan/_pipeline/patterns.py:1–58` is a **compatibility facade** re-exporting from
`pattern_topology` / `pattern_dynamic` / `pattern_joins` / `pattern_types`. Formalize:

- **F1 — `critique_revise_gate_loop`** (`pattern_topology.py:47`). Emits **exactly four hard-coded
  `kind="gate"` edges** `iterate/proceed/tiebreaker/escalate` (`pattern_topology.py:79–82`, params
  `on_proceed/on_iterate/on_tiebreaker/on_escalate` at `:52–55`). Rewrite so edges are driven by the M2
  gate consequence + **caller-supplied verdict labels**, not the baked-in 4-enum. Declare its Ports
  (consumes a draft artifact + a critique; produces a gated/revised artifact).
- **F3 — `escalate`/deadlock**: `escalate_if(condition, escalation_handler)→(Step, Edge)`
  (`pattern_topology.py:301`, escape edge `kind="gate"`, `recommendation="escalate"` at `:318–321`) +
  `subpipeline_call` (`pattern_topology.py:193`, wraps a child pipeline as `SubloopStep` with a `promote`
  fn at `:196,214–217`). Formalize the two into **one** node-library entry: "gate-unresolved → run a
  deadlock-breaker subpipeline → promote the result back to a routing key," on M2 Ports, routing the
  divergent case via the M3 `restore_and_diverge` consequence.
- **F9 — formalize the surface**: declare `patterns` the documented vocabulary; attach a stability tier to
  each exported node; reserve `arnold_api_version`. Re-point `JoinFn`/`PromoteFn` off `GateRecommendation`.
- **The type leaks to remove (TWO modules, not one):**
  - `pattern_types.py:14,16` — `from ...types import GateRecommendation` and
    `PromoteFn = Callable[[dict[str, Any]], GateRecommendation]`. Re-type `PromoteFn` to return the M2
    **routing-key** type (REGISTER §M5a: "PromoteFn → returns the M2 routing-key type"); drop the import.
  - `pattern_joins.py:8–13,17–73` — `majority_vote` (`:17`) + `weighted_vote` (`:46`) import
    `GateRecommendation` from `...types` (`:10`) and tally/return it. The vote nodes must tally
    **caller-supplied labels** (`Reduce[T]` over a structured result), not the planning 4-enum, so the
    SDK-module grep gate passes with `pattern_joins.py` in scope. *(Prior draft missed this second leak.)*
- **Supporting nodes to tier + Port-annotate (touched, not redesigned):** `panel_parallel`
  (`pattern_topology.py:100`, fan-out → `{reviewer_id}.{label}` join at `:138–146`), `panel_from_artifact`
  (`pattern_dynamic.py:131`), `dynamic_fanout` (`pattern_dynamic.py:148`), `iterate_until_consensus`
  (`pattern_dynamic.py:240`), `paired_round` (`pattern_dynamic.py:301`), `iterate_until`
  (`pattern_topology.py:269` — its dropped predicate is wired by M3, not here), `alternating_turns`
  (`pattern_topology.py:152`), `mode_prompts` (`:222`), `phase_zero_gate` (`:326`).
- **R6 — Behavioral Identity Manifest** (new): `manifest.py` (or `_pipeline/identity.py`) with
  `behavioral_manifest(realized_graph, run_config) -> ManifestHash`. Hashes the closure per SYNTHESIS
  §297–305: graph topology + per-Step **code hashes** (not class names) + resolved prompt **bodies**
  (text) + routing decision **taken** + the Port set + the SDK/ABI version (`arnold_api_version`) + the
  resolved dep-closure (P@hash of every composed node). M3's resume policy is re-pointed to key on the
  Manifest hash (pin/refuse/migrate-via-codemod) — landed default-OFF behind the M3 flag (see Constraints).

---

## Locked decisions

- **Built on M2 Ports, not `GateRecommendation`.** No node in the published surface may import or return
  `GateRecommendation` (it lives in the planning app after M2). Verdict labels are caller-supplied; the
  grep gate runs with `pattern_types.py` AND `pattern_joins.py` in scope.
- **Each node declares its Ports** (consumes/produces) so M1's `pipelines check` can statically verify a
  composition built from node-library nodes is wired.
- **Stability tier on every node, lightweight registry.** Tier metadata is a **registry dict keyed by
  export name** (REGISTER §M5a) — not a decorator, not a `Node` wrapper — so the facade and the
  contract-checker read it without eagerly importing the implementation (the non-executing-discovery
  constraint, EPIC §200). Assignment: **F1/F3 + the formalized macros = `provisional`** (the epic keeps
  reshaping them through M5b–M5d/M6); `_*` helpers = `internal`; only signatures the epic commits not to
  break = `stable`; **default `provisional`**.
- **Reserve `arnold_api_version` in BOTH forms** (REGISTER §M5a): a module-level constant on `patterns.py`
  AND a tier-table field M6 reads. M5a only needs the value to exist and the tier table to reference it.
- **`escalate`/deadlock = ONE node** = `escalate_if` + `subpipeline_call` formalized into one entry; the
  divergent-subpipeline case routes via the M3 `restore_and_diverge` consequence.
- **R6 Manifest hashes the realized graph** M3 produces (the closure, not the output file); **M3's resume
  policy keys on the Manifest hash**. The Manifest function is pure/deterministic over its inputs.
- **No new verbs** (EPIC §62, §145): decoupling + formalization + tiering + the Manifest hash only.
- **Back-compat:** keep `patterns.py` re-exports + `__all__` valid (`patterns.py:40–58`); name aliases
  preserved; the characterization import-surface test stays green.

## Open questions — each RESOLVED to its default (REGISTER §M5a, zero human blockers)

1. **Tier metadata shape** → lightweight **registry dict keyed by export name** (checker-readable, no
   eager import). *Locked.*
2. **`PromoteFn` target type** → returns the **M2 routing-key type** (the binding maps key→consequence);
   re-type against the real M2 surface name, not a placeholder. *Locked.*
3. **Where `arnold_api_version` lives** → reserve in **both** a `patterns.py` module constant AND a
   tier-table field M6 reads. *Locked.*
4. **R6 Manifest home/scope** (not in REGISTER §M5a verbatim, resolved to the most-conservative default):
   land as a pure `behavioral_manifest()` function consuming M3's realized graph; M3 resume keys on it
   **behind the existing M3 default-OFF flag** — no new flag, no new substrate. *Default-resolved.*

## Constraints

- Do not start before M2's ZERO-`GateRecommendation` grep gate is green (partial conversion is worse than
  none — SYNTHESIS, EPIC §138/§265). Merge gate: **grep=0 (with `pattern_types.py` + `pattern_joins.py`
  in scope) AND all consumers green together** — never a partial merge.
- **Strangler discipline** (PROGRAM §361–389): every change lands `{old-path default-ON, new-path
  default-OFF behind a flag}`. R6 + the Manifest-keyed resume ride M3's existing default-OFF
  `MEGAPLAN_UNIFIED_DISPATCH`; the epic driving the build runs the toggle OFF on the pinned/frozen old
  engine. **No organ-swap + old-path deletion in one PR.** The sole retirement authority is the
  behavioral-replay + substrate-swap ORACLE, never the happy-path parity gate.
- **Parity gate stays green & honestly labelled** (control-flow/artifact parity on the happy path, NOT
  drift-provably-zero): re-typing `critique_revise_gate_loop`'s edges must produce the **identical four**
  planning edges when planning supplies its 4 labels.
- **No silent gate auto-downgrade regression** (`project_gate_tiebreaker_downgrade.md`): F1's
  verdict-fidelity (the four planning edges still route correctly) must hold; the vote nodes' tiebreaker
  default must not silently downgrade a real verdict.
- Don't dogfood off an editable install; schema report-only (`project_dogfood_engine_shadow_and_openrouter.md`).

## Done criteria (testable; incl. the oracle gate)

- [ ] `pattern_types.py` AND `pattern_joins.py` no longer import or return `GateRecommendation`;
      `PromoteFn`/`JoinFn`/the vote nodes return structured M2 types (routing key / `Reduce[T]`); the M2
      SDK-module grep gate stays green with BOTH modules in scope.
- [ ] `critique_revise_gate_loop` (F1) is parameterized on caller-supplied verdict labels + the M2 gate
      consequence; with planning's 4 labels it emits the identical `iterate/proceed/tiebreaker/escalate`
      edges (parity test green).
- [ ] `escalate`/deadlock (F3) is ONE published node-library entry combining `escalate_if` +
      `subpipeline_call`, on M2 Ports, routing the divergent case via `restore_and_diverge`.
- [ ] Every exported node declares consumed/produced Ports and carries a stability tier; F1/F3 + formalized
      macros are `provisional`, `_*` are `internal`, default is `provisional`.
- [ ] `arnold_api_version` exists as a `patterns.py` module constant AND a tier-table field; the tier table
      references it.
- [ ] M1's `pipelines check` reads each node's Ports and statically verifies a composition built from them.
- [ ] **R6:** `behavioral_manifest()` returns a stable hash over {topology + Step-code hashes + resolved
      prompt bodies + routing-taken + Port set + ABI version + dep-closure}; two structurally-identical
      runs hash equal, and a changed prompt body / changed routing / changed Step code each flips the hash
      (unit-asserted). M3's resume keys on the Manifest hash (pin/refuse/migrate-via-codemod), behind the
      M3 flag.
- [ ] `patterns.py` is the documented public vocabulary; `__all__` + re-exports unchanged for back-compat;
      `tests/characterization/test_import_surface.py` passes.
- [ ] **ORACLE GATE (sole retirement authority):** a planning-shaped throwaway plan composed from the
      formalized node library runs behind the M3 default-OFF flag and the behavioral-replay oracle confirms
      it matches recorded REAL-run traces — including a recorded escalate/tiebreaker trace exercising the
      new F1 edges and the F3 deadlock-breaker (not happy-path-only). Red auto-halts/reverts or runs the
      bounded escalation ladder (retry ×2 → bump profile/robustness one tier → `stop_chain` + auto-ticket),
      never parks on a human (PROGRAM §388–389, REGISTER §2).

## Touchpoints

`megaplan/_pipeline/patterns.py` (facade + tier table + `arnold_api_version`), `pattern_topology.py`
(F1/F3 + tier annotation), `pattern_dynamic.py` + `pattern_joins.py` (tier + Port annotation of fan-out/
vote nodes; `GateRecommendation` removal from the vote joins), `pattern_types.py` (`PromoteFn` re-type +
`GateRecommendation` removal), `_pipeline/subloop.py` (F3 `SubloopStep`/`promote` re-type — `promote:
Callable[..., GateRecommendation]` at `subloop.py:68` must follow `PromoteFn`), new `manifest.py` /
`_pipeline/identity.py` (R6), the M3 resume path (re-point to the Manifest hash, behind the M3 flag).
Tests: `tests/characterization/test_import_surface.py`, the M1 contract-checker, the
`critique_revise_gate_loop` parity test, the R6 manifest-determinism units, the behavioral-replay oracle.
Planning bindings (`handlers/gate.py` 4-label/consequence wiring) are touched ONLY where the re-type
forces it; the binding rewrite proper is later-M5, not M5a.

## Anti-scope

- **The execute task-DAG (M5b)** — F4 complexity-tiering / F5 produce-process scheduler; not here.
- **The control plane (M5c)** — run-outcome vocabulary, the 9 override actions, `workflow_next` projection,
  the `STATE_*` eviction.
- **The supervisor tier (M5d)** — chain/epic/bakeoff cross-run orchestration.
- **The Evaluand/Calibration (M5-eval/M5-cal)** — versioned attributable judgments + routing-as-a-query.
- **F2's three-substrate `fan_out` unification** behind M4 dispatch — M5a tiers + Port-annotates the
  existing `panel_parallel`/`dynamic_fanout` nodes but does NOT merge the subprocess/async/thread substrates.
- New verbs; planning prompt/rubric re-tuning; the M6 relocation + `_BUILTIN_NAMES` drop + the Replayable
  Capsule (M7-capsule, which is a projection OFF the Manifest M5a lands).
