# Forbidden-terms baseline loop — single source of truth

> Fix plan for the recurring `manual_review` halt on
> `extension-reality-chain-restart-continuation`.
> Status: DRAFT (pending Codex high-reasoning sense-check). Owner: POM + Claude.

## TL;DR

A boundary test (`test_generator_source_does_not_add_new_forbidden_patterns`) is
**false-positiving on a detector** — a brand-new AST import-scanner added to
`scripts/generate_native_representation_evidence.py` **today** (`70b7e7d5b4`,
"Add S7 native parity standalone modules and tests") hardcodes the very forbidden
string (`arnold.pipelines.megaplan`) it is built to detect. That failure is not in
`baseline_test_failures`, so the finalize gate blocks → `manual_review`. The
superfixer correctly parks it (no autonomous remedy exists for a baseline-gate
contradiction) and the watchdog re-emits the human-review warning **hourly**.

**Fix:** promote `FORBIDDEN_AUTHORING_TERMS` to a shared `arnold/conformance/`
module so scanners *reference* the constant instead of *hardcoding the literal*.
The literal leaves the scanned tree, the test passes genuinely, and a drift test
locks the door behind it.

---

## The bug

### Symptom — the recurring halt

Session `extension-reality-chain-restart-continuation`, plan
`make-extension-reality-chain-20260708-1450`, task **T5**:

- `pytest` (focused set): `1 failed, 424 passed in 216.70s`
- only failure: `tests/docs/test_m5_generated_scans.py::test_generator_source_does_not_add_new_forbidden_patterns`
- failure **not** in `baseline_test_failures` (`finalize.json`) → `execution_blocked` → `manual_review`
- tier escalation `deepseek-v4-flash → deepseek-v4-pro → gpt-5.5` cannot help — this is not a model-capability problem
- watchdog classifies `AMBIGUOUS_BLOCKER` → `action: observe` → human-review warning re-emitted every cycle (14:04, 15:06, 16:07 UTC today, 2026-07-09)

### Root cause — a false positive on the detector itself

The test (`tests/docs/test_m5_generated_scans.py:182`) is a **substring scan**:
it greps every `.py` under `scripts/` for any of `FORBIDDEN_AUTHORING_TERMS` and
asserts zero hits. It cannot tell a *detection* from an *authoring violation*.

The new scanner at `scripts/generate_native_representation_evidence.py:1140-1146`
(added today by `70b7e7d5b4`) hardcodes the literal **4×**:

```python
if alias.name == "arnold.pipelines.megaplan" or alias.name.startswith(
    "arnold.pipelines.megaplan."
):
    hits.add(alias.name)
...
if node.module == "arnold.pipelines.megaplan" or node.module.startswith(
    "arnold.pipelines.megaplan."
):
    hits.add(node.module)
```

This code **is** the detector — it walks the AST hunting for illegal
`arnold.pipelines.megaplan` imports (the old dotted path, post-migration). The
literal must be present for the comparison to work. The test flags its own
detector → 4 hits, every run.

> Note: the halt reports `commits=88084317` ("Remove consolidation runtime
> residue"), but that commit did **not** touch this file (4 files, 522 deletions).
> `88084317` is merely the chain's HEAD tip. The offending code is `70b7e7d5b4`.

### Why a shared constant is safe

The test scans only `(REPO_ROOT / "scripts").rglob("*.py")` (plus an
`ARCHIVAL_OR_PENDING_PATHS` skip list). A constant living under `arnold/` is
**never scanned**, so moving the literal out of `scripts/` makes the test pass
without weakening it.

### Why the superfixer didn't (and shouldn't) auto-fix it

L1 repair-loop ran (13:03 UTC today): `source-initiative-repair` succeeded;
`source-workspace-repair` and `dependency-manifest-repair` returned
"not applicable (status=2)." Its repertoire is broken-source / workspace /
dependency — none applies to a **baseline-gate contradiction**. The classifier
then returned `AMBIGUOUS_BLOCKER` → `action: observe` → human review.

This is **correct, not broken**: the only ways to turn the red green autonomously
are guard-weakening — delete/relax the test, or silently add the failure to the
baseline — exactly what the fixer must never do unsupervised. It parked the
session for a human, which is the safe failure mode. The real defect is upstream
(test + baseline disagree about what counts as a violation), not in the repair
stack.

> Ruled out: the documented `//arnold_pipelines/...` meta-repair double-slash
> retrigger bug — **zero** such events for this session (that belonged to the
> older `megaplan-native-parity-corrective` session).

---

## The solution

### Track 1 — single source of truth for forbidden terms (unblocks + prevents)

1. **New module `arnold/conformance/authoring_terms.py`** exporting, moved
   verbatim from the test:
   - `FORBIDDEN_AUTHORING_TERMS` (the 9-term tuple, `test_m5_generated_scans.py:78`)
   - `FORBIDDEN_COMMAND_TERMS` (`test_m5_generated_scans.py:90`)
   - `FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES = ("arnold.pipelines.megaplan",)` — the
     subset of authoring terms that are import-path prefixes, for use by scanners.

   Lives under `arnold/` → not self-scanned.

2. **Generator** (`scripts/generate_native_representation_evidence.py:1140-1146`):
   import the prefix tuple; replace the 4 hardcoded literals with iteration:

   ```python
   for prefix in FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES:
       if alias.name == prefix or alias.name.startswith(prefix + "."):
           hits.add(alias.name)
   # (same shape for the ImportFrom branch)
   ```

   Behavior is preserved exactly (exact-match OR dotted-prefix). The literal
   `"arnold.pipelines.megaplan"` no longer appears in the generator's source →
   the substring test stops tripping.

3. **Test** (`tests/docs/test_m5_generated_scans.py:78`): replace the local
   `FORBIDDEN_AUTHORING_TERMS = (...)` / `FORBIDDEN_COMMAND_TERMS = (...)`
   definitions with imports from `arnold.conformance.authoring_terms`. Single
   source of truth.

### Sibling scanner (found during sense-check — non-blocking)

`scripts/check_workflow_pipeline_inventory.py:165` **also** hardcodes
`"arnold.pipelines.megaplan"`. It is NOT part of the current failure because it
sits on the test's `ARCHIVAL_OR_PENDING_PATHS` skip list
(`test_m5_generated_scans.py:62`). Refactor it to the shared constant too, so it
won't trip the moment it's ever taken off the skip list.

Sense-check also confirmed the generator already imports `arnold.conformance.*`
(`checks`, `deleted_surfaces`) — so adding `authoring_terms` is import-cycle-safe.

### Track 2 (prevent) — lock the door

4. **Drift test** (new, e.g. in `tests/docs/test_m5_generated_scans.py` or a
   sibling): assert
   - `FORBIDDEN_AUTHORING_TERMS` / `FORBIDDEN_COMMAND_TERMS` have exactly one
     definition repo-wide, in `arnold/conformance/authoring_terms.py`;
   - `test_m5_generated_scans` imports (not defines) them;
   - every entry in `FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES` is present in
     `FORBIDDEN_AUTHORING_TERMS` (so scanners can't drift from the canonical set).

   The existing `test_generator_source_does_not_add_new_forbidden_patterns`
   already prevents literals re-entering `scripts/` — that guard worked perfectly
   (it caught today's regression). This drift test only guarantees the constant
   itself can't fragment.

### Track 2 (recover) — FOLLOW-UP, out of scope for this execution

The hourly spam and the "parked forever" gap are real but live in the
watchdog / repair-dispatch path; they are a separate planned unit:

- **De-duplicate identical human-review notifications** (emit once, suppress
  until state changes) — directly kills the recurring `#2172`-style spam.
- **Precise classification**: teach `needs_human_fresh_classifier` to recognize
  "non-baseline failure in a forbidden-pattern *self-scan*, hits inside the
  detector's own code" as a candidate false-positive with an actionable prompt,
  instead of generic `AMBIGUOUS_BLOCKER`.
- **Deterministic-failure circuit breaker** on the observe loop (N identical
  halts with no state change → one consolidated signal).

These touch live repair-dispatch behavior and warrant their own review. Not in
this pass.

---

## Execution

**Venue:** a local git worktree off `editible-install` (keeps the dirty `main`
working tree untouched; uses proper editing tools). Push; the box pulls into
`/workspace/arnold`; re-trigger; verify.

1. `git worktree add` on `editible-install`; confirm its SHA matches the box's
   `editible-install` HEAD (deploy self-consistency — half-committed imports kill
   sibling chains on restart).
2. Apply changes 1–4 above.
3. Local sanity: `pytest tests/docs/test_m5_generated_scans.py -q` → green.
4. Commit + push `editible-install`.
5. Box: pull into `/workspace/arnold`; run the executor's focused set —
   `tests/test_chain_completion_guard.py tests/cloud/test_status_snapshot.py
   tests/cloud/test_watchdog_wrappers.py tests/docs/test_m5_generated_scans.py`
   → green.
6. Re-trigger L1 repair on `extension-reality-chain-restart-continuation`; verify
   plan `make-extension-reality-chain-20260708-1450` **advances past T5** (not
   merely that something restarted).

## Verification — done iff all true

- [ ] `test_generator_source_does_not_add_new_forbidden_patterns` passes.
- [ ] `grep -rn "arnold.pipelines.megaplan" scripts/generate_native_representation_evidence.py` → zero hits.
- [ ] drift test passes; constants defined exactly once.
- [ ] focused 4-test set green on the box.
- [ ] session advances past T5; no new `manual_review` halt for this cause.
- [ ] `editible-install` pushed; box `/workspace/arnold` at the fix SHA.

---

## Follow-ups / out of scope

- Track 2 recover (notification de-dup, classifier precision, circuit breaker) — separate planned unit.
- Local `megaplan` CLI is a **dangling symlink** (`~/.local/bin/megaplan` → missing `/Users/peteromalley/Documents/megaplan/.venv`); unrelated to this bug but blocks local `megaplan cloud` use. Worth fixing separately.
