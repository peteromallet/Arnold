# Sprint 1 — Safety net + correctness (`premium/thorough/high +prep`)

Shared context: read `docs/structural_audit_2026-05.md` (both parts) for the full findings this epic addresses. This is sprint 1 of 7 in the "make VibeComfy excellent" epic. VibeComfy is a Python package that drives ComfyUI from Python: an editable IR (`VibeWorkflow`) compiles to ComfyUI API JSON; raw JSON workflows under `ready_templates/sources/` are converted by the emitter (`vibecomfy/porting/`) into curated Python "ready templates" under `ready_templates/`.

## Outcome
Fix the emitter's value-corruption bug at its root, re-emit every affected ready-template correctly, and stand up the safety net — a differential round-trip test harness plus an *armed* parity gate — so emitter-fidelity regressions can never ship silently again.

The harness must be built **failing-first**: before remediation, it should reproduce the known corrupted templates and fail on the expected value/type mismatches. Only after that red state is captured should the emitter fix and re-emission happen.

## Scope (IN)
1. **Diagnose & fix the positional-desync root cause** in `vibecomfy/porting/emitter.py`: the mismatch between the `input_items` and `widgets_values` arrays in `_subgraph_instance_widget_values` (~line 2765), which feeds wrong values into `_subgraph_call_kwargs` (~2648) and `_node_kwargs` (~3348). Symptom: named params receive wrong-typed values (e.g. `steps=<seed-magnitude int>`, `cfg='randomize'`, `voice=<bignum>`, `seed='randomize'`).
2. **Build a differential round-trip harness** (`tests/test_template_roundtrip.py` + helper): for every ready_template, load → `compile("api")` → compare semantically against the source corpus JSON (widget values, value *types*, edges). Must catch seed→steps, control_after_generate→cfg, voice=bignum, unload_models=bignum.
3. **Re-emit all corrupted templates.** Confirmed value-corruption set is locked from the intersection of the audit's j2 finding and the failing-first harness output. The seed set is `image/z_image` (`steps`/`cfg`) and `video/ltx2_3_runexx_talking_avatar_qwen_tts` (`voice`/`unload_models`/`seed`); `prep-m1.md` must enumerate every additional audit-flagged template before the harness runs, and `handoff-m1.md` records any additions discovered by the harness. Also resolve `widget_N=''` / unresolved-alias leaks where the schema makes them resolvable. Any `widget_N=''` mapping to a known ComfyUI/widget schema must be resolved; only custom-node widgets with no discoverable schema may be documented as unresolved.
4. **Re-arm the swallowed convert-equivalence parity gate** at `vibecomfy/porting/convert.py:315-370` — the ~55-line compile/build/compare block currently wrapped in `except Exception: pass`. Make failures loud and surfaced. This is distinct from the existing canonical-baseline parity workflow (`tools.check_canonical_parity`); CI must exercise both the canonical-baseline check and the armed `port convert` equivalence path.
5. **Fix the conftest marker bug** (`tests/conftest.py` ~line 85): the `and` that should be `or`, which makes `--runpod-full` silently deselect regular `runpod` tests.
6. **Reconcile docs with reality**: `CLAUDE.md` cites `scripts/materialize_ready_templates.py` which does not exist; the real path is `cli port convert`. Fix the reference.
7. **Create the safety-net handoff artifact** at `docs/megaplan_chains/excellence_epic/handoff-m1.md`, recording the harness command, known failing-first evidence, re-emitted template list, intentional snapshot deltas, human-reviewed correction rationale for each snapshot delta, and any deferred widget-alias/schema gaps.

## Locked decisions
- The differential harness is the canonical regression net (not snapshot-only); snapshots stay as a secondary check.
- Add at least one heterogeneous oracle lane: a hand-curated golden API JSON fixture at `tests/fixtures/golden_api_video_wan_i2v.json`, reviewed against ComfyUI API JSON semantics and committed as raw API JSON, then compared against the live template's `build().compile("api")` output. If the fixture is derived from `docs/templates/examples/gold_template_wan_i2v.py`, record the provenance and human review notes in `handoff-m1.md`. If that source file does not exist, bootstrap the fixture from a direct ComfyUI API JSON export for the equivalent workflow, or from a hand-constructed minimal API JSON fixture with explicit reviewer attestation; record the source command/path and reviewer/date. Do not treat an unreviewed emitter output snapshot as independent evidence. Existing Python-template alignment tests remain secondary.
- The parity gate must FAIL CI when armed.
- Re-emission will change committed snapshots; regenerate them, and justify each diff by the differential test.
- Dead node-spec deletion moves to sprint 2b, where consistency gates can prove the post-delete registry is intact.

## Prep deliverables
- Map the exact mechanism of the positional desync: `input_items`/`widgets_values` construction and how non-widget UI entries break alignment.
- Classify each `widget_N=''` leak as alias-resolvable or schema-addition-needed. Alias-resolvable leaks are fixed in this sprint; schema additions are documented in `handoff-m1.md`.
- Prep deliverable: a short markdown note committed under `docs/megaplan_chains/excellence_epic/prep-m1.md` that maps the desync path, enumerates the audit j2 corruption set, identifies the failing-first fixture set, and names the exact commands the sprint will use for red/green evidence.

## Constraints
- Every re-emitted template must compile and pass the differential harness.
- No IR or runtime behavior changes in this sprint (those are sprints 3/6).
- Snapshot regeneration must be auditable.
- Downstream-gate contract: later sprints must continue to run this differential harness before merge.

## Done criteria
1. Differential harness has a committed failing-first record at `tests/fixtures/failing_first_m1_corruptions.json` against the known corrupted templates, then passes for 100% of `ready_templates/` after the fix. The JSON artifact is an array of `{template_id, node_id, field, wrong_value, wrong_type, expected_type}` entries and is committed before any emitter fix. "Pass" means the harness fails when any widget value differs by type or equality, any edge source/target differs, or the node set differs; the corruption fixture must be generated or regenerated by the harness command recorded in `handoff-m1.md`, not hand-written.
2. Convert-equivalence parity gate armed and exercised in CI alongside the existing canonical-baseline parity check.
3. Heterogeneous golden-JSON lane exists for at least one representative ready template and is independent of the emitter's own canonicalizer path. `handoff-m1.md` records provenance for the fixture: source of API JSON, reviewer/date, and at least three semantic assertions verified by inspection. If the fixture is derived from emitter output, the sprint is not done.
4. The ~8 value-corruption templates verified right-typed by explicit `type(value)` assertions (`steps`, `cfg`, `seed`, `voice`, `unload_models`).
5. Fast suite command green: `pytest -q --tb=short --ignore=tests/test_models_registry.py --ignore=tests/test_runpod_runner.py --cov=vibecomfy --cov-report=term-missing --cov-report=xml`; any intentional deviation from the current `ci.yml` command is recorded in `handoff-m1.md`.
6. `--runpod` and `--runpod-full` flags correctly select/deselect their respective test sets, verified by a dedicated fast-suite test for the conftest marker bug.
7. Snapshot assertions in the fast suite pass; snapshot regeneration, if needed, has an explicit command or manual provenance recorded in `handoff-m1.md`.
8. Docs match reality and `handoff-m1.md` captures commands, artifacts, human-reviewed snapshot-delta rationale, and deferred risks.

## Touchpoints
`vibecomfy/porting/emitter.py`, `convert.py`; `ready_templates/**`; `tests/conftest.py`, new `tests/test_template_roundtrip.py`; `CLAUDE.md`; `docs/`.

## Anti-scope
Do NOT decompose `emitter.py` (sprint 5). Do NOT change `set_input`/`compile` IR semantics (sprint 3). Do NOT delete stale node-spec files (sprint 2b). Do NOT build the broader consistency gates (sprint 2a) — only the parity gate + differential harness here.
