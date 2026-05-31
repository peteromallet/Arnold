# M1 — Foundation, hygiene, contract-checker + R1 shadow-WAL seed + seeded facts

**Status:** Re-aimed 2026-05-29 onto the sequenced program of record
(`.megaplan/briefs/validation/sequencing/PROGRAM.md` — the M1 entry L84–103; critical path L340; strangler
discipline L361–389; open risks #2 L428–435) and the eleven-organ architecture
(`.megaplan/briefs/pipeline-unification-EPIC.md` §"The architecture" L23–84, §"Sequenced build program — FINAL"
L225–258). Organ specs: `.megaplan/briefs/validation/committed-uu/SYNTHESIS.md` Reshaper #1 (L69, L343–348),
R7 model-identity (L75, L385–388), Effect Ledger (L259–266), design principles #1/#2/#3/#10/#14
(L445–514). Human blockers all resolved to defaults: `.megaplan/briefs/validation/human-blockers/REGISTER.md`
§3 M1 line (L104). All file:line **re-verified against current code** (`megaplan/__init__.py:46`
`__version__ = "0.23.0"`).

## Outcome
The repo is made safe to refactor on top of, **and** the un-retrofittable seeds the architecture needs
while there is still exactly one author/tenant are planted — both as standalone PRs landing the day they
go green. The hygiene half is unchanged from the prior draft (CI runs the real suite; the executor is one
override-complete path; a schema revert can't strand in-flight plans; cloud SSH + `status` JSON are
pinned; discovery is loud; the sandbox/stall foot-guns are closed; `pipelines check/doctor/new` + the
`chain.yaml↔EPIC↔briefs` lint make the executable artifact un-able to lie). The **new, load-bearing**
half: the **R1 shadow-WAL** — every state-changing event also appended to an append-only, effect-typed,
taint-carrying log with a per-milestone fold-equivalence assertion against `state.json`, **`state.json`
still the sole authority** (Reshaper #1 seeded, not flipped — the flip is M3). Plus three cheap seeds the
value lens demands now: **R7** model-identity as a hash-pinned receipt field (recorded, no consumer);
the **Effect-Ledger TYPE skeleton** (replay-class enum + idempotency-key field, declared not enforced);
and the M1 **sensors** (per-phase prefix-cache-hit-rate + monoculture index) + the
**ZERO-`GateRecommendation` grep-gate scaffold** that enforces de-planning from line one. Nothing here
changes SDK/pipeline *types*, relocates a pack, flips any authority, or enforces any new world-act
contract.

## Scope (work items — each a standalone PR; tied to current file:line)

**W1 — CI marker-switch.** `.github/workflows/ci.yml:21` runs a hardcoded 4-file list
(`test_import_surface.py test_pipeline_run_cli.py test_cloud_template.py test_cloud_spec.py`); the parity
gate, chain-status contract, editorial/resolutions tests never run. Replace with `pytest -m "not slow" -q`.
Keep the docker job (`ci.yml:37`) advisory `continue-on-error`. Hermetic, key-free under
`MEGAPLAN_MOCK_WORKERS=1`.

**W2 — executor-merge superset.** `run_pipeline` (`executor.py:212`) is the only production path;
`run_pipeline_with_policy` (`executor.py:308`) has zero production callers. Merge as a **superset onto
`run_pipeline`** with `policy: RuntimePolicy | None = None` — never a swap. The bare path imports
`find_override_edge` (`executor.py:273,278`); the policy variant does not, so routing prod through it
silently drops override edges. Keep `run_pipeline`'s full ladder (override → recommendation/escalate →
normal) as the base; gate policy-only guards behind `if policy is not None`, so `policy=None` (= all prod)
is byte-for-byte unchanged. `run_pipeline_with_policy` becomes a thin shim that keeps its
`TypeError`-on-non-`RuntimePolicy` contract (`executor.py:332`). Do NOT touch `run_pipeline_by_name`
(`registry.py:205`), `auto.py`, or `MEGAPLAN_PIPELINE_AUTO`.

**W3 — state back-compat + fixture corpus.** `StorageModel.model_config = ConfigDict(extra="forbid", …)`
(`schemas/base.py:37`) makes any forward bump non-revertible. (a) `extra="forbid"` → `extra="ignore"` on
`StorageModel`. (b) Add `schema_version: int = 0` to `Plan` (`schemas/sprint1.py:215`), absent ⇒ 0/legacy,
never reject. (c) In `_apply_legacy_state_migration` (`state.py:293`, on the
`load_plan_from_dir` `state.py:93` → migrate → validate path) add a migrate-before-validate branch
stamping absent `schema_version`. (d) Build fixture corpus
`tests/fixtures/state_json/{v0_noversion,v1,v_future}/state.json` + a load-and-resume test. (e) Same
forgiving treatment for `chain_state.json`.

**W4 — pin status + chain contracts.** Extend `tests/characterization/test_import_surface.py`. The four
`megaplan.chain` SSH names are already asserted (`test_import_surface.py:17–20,165–179`) — verify and keep
as a named contract block. **Add** a `status` JSON contract test pinning the key set of
`_build_status_payload` (`cli/status_view.py:747`, returned by `handle_status` `:885,901`), consumed by
cloud over SSH and not yet pinned. No version-skew check yet (M3).

**W5 — discovery-integrity guard.** `discover_python_pipelines` (`registry.py:360`) silently skips modules
whose load returns None / lack a callable `build_pipeline` (`registry.py:399–401`) and `_BUILTIN_NAMES`
collisions with only a `UserWarning` (`registry.py:382–388`). Make discovery **fail-loud in-tree** and
**report-loud for user packs** (`~/.megaplan/pipelines/`, reasons carried into W7's `doctor`). This is the
guard preventing `get_pipeline("planning")` `KeyError` when M6 relocates planning. M1 only adds the guard;
it does NOT drop `_BUILTIN_NAMES` (`registry.py:53` = `frozenset({"planning"})`).

**W6 — sandbox/stall foot-gun fixes.** `install_sandbox` (`sandbox.py:376`) already raises on a missing
`project_dir` (`sandbox.py:392`) — characterize that fail-closed behavior with a test. Close the
fail-**OPEN** gap: when `SANDBOX_CWD` is None the wrappers delegate unchanged (`sandbox.py:87,383`); assert
the intended per-call `project_dir` is actually installed on the hermes worker path (`hermes.py:1063`,
`project_dir` resolved `hermes.py:729`) so a phase can't silently run un-sandboxed.

**W7 — contract-checker / diagnostic discovery / scaffold.** Add a `pipelines` command group
(`cli/parser.py:331` sibling of `list pipelines`; `cli/__init__.py:1307`):
- **`pipelines check [<name>]`** → static `validate(Pipeline) -> Diagnostics` WITHOUT dispatch: every
  `Edge.target` (`types.py:82,97`) names a real stage in `Pipeline.stages` (`types.py:237`) or `halt`; no
  `halt` as an edge *label*; every gate stage's `Edge.recommendation` set covers the `GateRecommendation`
  literals (`types.py:76,104,129`) — gate verdicts have matching edges; no stage unreachable from `entry`.
  Exit non-zero + name the defect. **Edges/reachability/gate-coverage only — no `consumes`↔`produces`
  Port resolution (that is M2; no `Port` type exists today).**
- **`pipelines doctor`** → per-path report from W5's reasons: discovered ✓ / rejected + traceback /
  skipped (reason) — kills the silent vanish at `registry.py:399–401`.
- **`pipelines new <name>`** → scaffold a `build_pipeline` module + SKILL.md stub passing `check` green.

**W8 — `chain.yaml↔EPIC↔briefs` lint.** Add a test/lint asserting the triple is 1:1: each `chain.yaml`
milestone `label` + `idea:` brief path (format per `.megaplan/briefs/hardening-epic/chain.yaml:19–127`) maps to a
milestone in the EPIC program (`PROGRAM.md` L69–332) and a real file in `.megaplan/briefs/epic-pipeline-unification/`
— count and ordering match, no orphan brief, no dangling path. NB `.megaplan/briefs/epic-pipeline-unification/
chain.yaml` does not exist yet (Open-Q #1, resolved below); the lint runs against whatever chain.yaml this
epic adopts and **fails loud if absent/empty**.

**W9 — R1 SHADOW-WAL writer (Reshaper #1 SEED).** A real append-only event journal already exists:
`observability/events.py` writes `events.ndjson` per plan via `EventWriter.emit` under `fcntl.flock` +
`os.fsync` (`events.py:122,150,189–215`) with a typed `EventKind` enum already covering
`STATE_TRANSITION`, `COST_RECORDED`, `LLM_CALL_*`, `ARTIFACT_WRITTEN` (`events.py:31,80–104`). W9 promotes
this from "telemetry beside `state.json`" to the **shadow-WAL**: (a) on every state-changing write
(`save_state` `state.py:210`; the `transaction`/atomic-replace path `state.py:346,436`) also append a
typed event carrying **effect-class**, a **taint** field (seeded `untrusted|trusted`, default-trusted
single-tenant), and a `schema_version` stamp; (b) a pure **fold** `fold_events(events) -> dict` that
rebuilds the plan-state projection from the log; (c) a **fold-equivalence assertion**
`assert_fold_equiv(plan_dir)` comparing `fold_events(read_events(...))` against the live `state.json`,
wired as a CI test over the W3 fixture corpus **and over the recorded-trace corpus M2.5 will add** (PROGRAM
risk #2 L428–435 — the fold must be validated against recovery/blocked traces, not just happy-path).
**`state.json` REMAINS the sole authority** (the flip is M3, gated on this oracle being green-since-M1).

**W10 — R7 model-identity seed + sensors (no consumer).** `cost.py` already records `model` into the
`COST_RECORDED` payload and classifies vendor by **substring** (`_classify_vendor` `cost.py:23`,
`payload.get("model")` `cost.py:101`) — exactly the UU#14 substring-smell. Seed (no behavior change, no
routing consumer): (a) add a **hash-pinned `model_identity`** field to the `COST_RECORDED` / `LLM_CALL_END`
payload = `hash(model_name + reported_version)` so weight-drift-behind-a-stable-name becomes a recorded
fact (R7, SYNTHESIS L385–388); (b) add **per-phase prefix-cache-hit-rate** and a **monoculture index**
(distinct-model fraction per run) as first-class derived metrics in the cost aggregate (`cost.py:71`
`_aggregate`) — sensors only, surfaced in `cost`/`doctor`, governing nothing (SYNTHESIS principle #14
L511–514). No `tier_models` read, no routing query (that is M5-cal).

**W11 — Effect-Ledger TYPE skeleton + grep-gate scaffold.** (a) Define a typed **`Effect` dataclass/enum**
— `replay_class ∈ {pure, idempotent_keyed, at_most_once, pivot}` + `idempotency_key: str | None`
(distinct from any content-hash) + `compensation: str | None` — and attach it as an **optional, unenforced**
field on the shadow-WAL event (W9). Declared shape only; **nothing enforces or branches on it** (enforcement
is M4, SYNTHESIS L489–491). (b) Land the **ZERO-`GateRecommendation` grep-gate** as a CI test that today
**asserts the current count and forbids growth** in SDK modules — `GateRecommendation` (`types.py:76`)
leaks via `PromoteFn` (`pattern_types.py:16`); the gate is a no-op-but-ratcheting scaffold now so M2's
conversion lands against a green, non-regressing baseline (REGISTER §3 M1, DC#1).

## Locked decisions
- Executor merge is a **superset onto `run_pipeline`**, `policy=None` default; never route prod through the
  policy variant. Policy-only guards stay dead/optional in M1.
- State fix = `extra="ignore"` + `schema_version: int = 0` (absent ⇒ legacy, migrate-before-validate, never
  reject); same for `chain_state.json`.
- CI = `pytest -m "not slow"`; docker stays advisory.
- Discovery guard added; `_BUILTIN_NAMES` **not** dropped (M6).
- `pipelines check` proves **graph wiring only**; Port `consumes` resolution is **M2**.
- **R1 is SEEDED, not flipped:** the shadow-WAL is written and fold-asserted every milestone;
  **`state.json` stays authoritative through M2.5.** The authority flip is M3, gated on this fold-oracle
  (green since M1) + the M3 substrate-swap oracle.
- R7 / Effect-class / taint are **recorded fields with NO consumer** in M1; the grep-gate **ratchets**
  (forbids growth) rather than requiring zero today.
- EPIC + brief set + `chain.yaml` are **one artifact triple**; W8 enforces it in CI.

## Open questions (each RESOLVED to its default — REGISTER §3 M1 L104; zero human waits)
- **chain.yaml provenance (blocking W8).** → **This epic authors its own
  `.megaplan/briefs/epic-pipeline-unification/chain.yaml`** (gives the lint a target); W8 fails loud until it exists
  (REGISTER: "lint the existing file, fail-loud-if-absent"; auto-arm on lint-green, §1 L42–46).
- **DB mirror.** `_PLAN_COLUMNS` (`_db/common.py:29`) has no `schema_version`. → **JSON path in M1; DB
  column deferred** (REGISTER: "schema_version → JSON-path in M1, DB column deferred").
- **Bare `run_pipeline` max_iterations cap.** → **NOT added in M1** — M4 owns budgets; do not smuggle a new
  prod behavior into the merge (REGISTER: "bare run_pipeline max_iterations cap → not added in M1").
- **Discovery boundary policy.** → **in-tree = fail-loud; user-pack = report-loud** (REGISTER DC#5).
- **Scaffold acceptance.** → **any green shape passing `pipelines check`** (REGISTER DC#8).
- **Where do R7 / cache / monoculture sensors live?** → **`cost.py` aggregate + `COST_RECORDED`/
  `LLM_CALL_END` payloads** — reusing the existing journal + aggregator, not a new store (SYNTHESIS #14;
  the existing substring classifier is the smell the seed begins to retire).
- **Shadow-WAL store?** → **reuse `events.ndjson`** (`observability/events.py`), already flock+fsync
  append-only — do not invent a second journal (the "two disjoint journals" UU#14 is unified at M6, not
  forked here).

## Constraints
- Don't dogfood off an editable install; pin the engine for any validation run (EPIC L314; memory
  `dogfood_engine_shadow`). M0 supplies the pinned engine; M1 runs under it.
- Schema + WAL + R7 + Effect fields are **report-only / forgiving / unenforced**, never fail-closed (EPIC
  L172–173, L315; SYNTHESIS principle #10 "before the first real act"; PROGRAM L91 "state.json still
  authoritative").
- Preserve all 26 `MEGAPLAN_*` env names, `handle_*` `__all__` shims, planning phase names valid in
  profiles; M1 must not regress any even incidentally.
- Re-run `test_pipeline_golden` + `test_pipeline_planning_parity` after W2 to confirm snapshot stability.
- Parity gate stays green & **honestly labelled**: "happy-path control-flow/artifact parity, NOT drift
  provably zero" (EPIC L315; PROGRAM L381–385) — remove any "drift provably zero" wording M1 touches; the
  fold-equivalence oracle (W9), not the parity gate, is the substrate authority.

## Done criteria (testable, incl. this milestone's oracle gate)
1. `ci.yml` runs `pytest -m "not slow"`; the parity gate + chain-status contract execute on PRs (>40 files
   run vs 4 today).
2. `run_pipeline(..., policy=None)` is byte-identical on all existing callers; `run_pipeline_with_policy` is
   a shim and its `TypeError` test + the policy-path test modules stay green with zero edits.
3. Reverting a `schema_version` stamp + reloading every `tests/fixtures/state_json/*` fixture resumes
   without `ValidationError` (proves `extra="ignore"`).
4. `test_import_surface.py` fails if any of the 4 chain SSH names OR a `status`-payload key is
   removed/renamed.
5. An in-tree pack with a broken/absent `build_pipeline` makes discovery **error**; a broken user pack makes
   it **report loud** (not silent at `registry.py:399–401`).
6. `install_sandbox` raises on missing project_dir (test); the hermes worker path installs per-call
   `project_dir` (test, `hermes.py:1063`).
7. `pipelines check` exits non-zero and names the defect on a mis-wired pipeline (edge to a non-existent
   stage; a gate verdict with no matching edge; an unreachable stage); exits zero on planning.
8. `pipelines doctor` lists every scanned module discovered/rejected+traceback/skipped; `pipelines new <n>`
   emits a package passing `check`.
9. The chain↔EPIC↔briefs lint fails when a label/idea-path/count diverges, or when chain.yaml is
   absent/empty.
10. **THE M1 ORACLE GATE (R1 fold-equivalence):** `assert_fold_equiv(plan_dir)` —
    `fold_events(read_events(plan_dir)) == live state.json` — passes for **every** W3 fixture and for every
    state-transition path exercised by the suite, runs as a required CI test, and is **wired to also run
    against the recorded-trace corpus the moment M2.5 lands** (this is the gate the M3 authority flip
    depends on being green-since-M1; per PROGRAM L386 it is the supplementary required gate, not the
    happy-path parity gate). A divergence auto-fails CI (machine-gate, no human wait).
11. The **grep-gate** test passes at the current `GateRecommendation`-in-SDK count and **fails on any
    increase**; the seeded `model_identity` / effect-class / taint fields are present in the WAL payload and
    asserted by a schema test, with **no module reading them to make a decision** (a grep proves zero
    consumers).
12. Per-phase prefix-cache-hit-rate + monoculture index appear in the `cost` aggregate output (sensor-only;
    no routing/gate consumes them).
13. No M1 doc or done-criterion contains "drift provably zero" wording.

## Touchpoints
`.github/workflows/ci.yml:21,37` · `megaplan/_pipeline/executor.py:212,273,308,332` ·
`megaplan/schemas/base.py:37` · `megaplan/schemas/sprint1.py:215` (`Plan`) ·
`megaplan/_core/state.py:93,210,293,346,436` · `megaplan/_pipeline/registry.py:53,205,360,382,399` ·
`megaplan/_pipeline/types.py:76,82,97,104,129,237` · `megaplan/_pipeline/pattern_types.py:16` ·
`megaplan/observability/events.py:31,80–104,122,150,189–215,294` (shadow-WAL substrate) ·
`megaplan/observability/cost.py:23,71,101` (R7 + sensors) ·
`tests/characterization/test_import_surface.py:17,165` · `megaplan/cli/status_view.py:747,885,901` ·
`megaplan/cli/parser.py:331` · `megaplan/cli/__init__.py:1307` ·
`megaplan/runtime/sandbox.py:87,376,392` · `megaplan/workers/hermes.py:729,1063` ·
`megaplan/cloud/supervise.py:54` · `.megaplan/briefs/hardening-epic/chain.yaml` (format ref) · new
`.megaplan/briefs/epic-pipeline-unification/chain.yaml` · new `tests/fixtures/state_json/` · new `pipelines`
command group + its lint test · new `fold_events`/`assert_fold_equiv` + the grep-gate test.

## Anti-scope
No SDK/pipeline **type** changes (no `JoinFn`/`Reduce`/`select`; no `Port`/`consumes`/`produces` — M2). No
pack **relocation** or `_BUILTIN_NAMES` drop (M6). No **feature extraction** into pieces/backends (M4/M5).
No subprocess→in-process port, realized-graph/topology-realizer, driver-axis split, routing rewrite, or
cost/liveness work (M3/M4). **No R1 AUTHORITY FLIP** — `state.json` stays authoritative; M1 only writes the
shadow-WAL + asserts fold-equivalence (the flip is M3). **No Effect ENFORCEMENT and no R7/taint CONSUMER** —
M1 records the fields; M4 enforces the Effect Ledger, M5-cal consumes R7, M3 carries the taint lattice on
the Envelope. No `GateRecommendation`→structured-data **conversion** (M2 — M1 only ratchets the grep-gate).
No auto.py / `run_pipeline_by_name` / `MEGAPLAN_PIPELINE_AUTO` wiring. No new prod behavior (e.g. a
max-iteration cap) smuggled into the executor merge. No HandlerContext signature migration (M5). No
manifest-first/non-executing discovery or trust tier (M6). No second journal — the shadow-WAL reuses
`events.ndjson`; journal unification is M6.
