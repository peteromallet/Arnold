# Judgment — m6b-deadcode-tests (milestone 12/12)

**Verdict:** FINE on the cleanup itself (split landed with exact 187=187 collection parity), but the milestone **bypassed megaplan's plan→critique→review→gate pipeline entirely** and was finished by a hand-driven merge — so the chain's declared `directed/light + adaptive_critique:true` config was a no-op, and a ~10h overnight idle stretched a ~4h job across 13h.

## Why this milestone bypassed the pipeline — and whether it mattered

The chain declares `vendor: codex / profile: directed / robustness: light / adaptive_critique: true`. The logs show none of that machinery ran. There are **0 actual `megaplan run/auto/chain` executions** — all 11 string hits are skill docs, CHANGELOG/PR text, or source being edited. Instead:

- **F3 (evening, in the worktree)** was the real m6b execute: it split `test_workers.py` into 9 concern modules + `_workers_helpers.py`, deleted the flat file, and self-asserted the hard gate (`--collect-only` = 187, matching baseline). It ended with **one open failure**: `test_step_schema_filenames_reference_existing_schemas` — `STEP_SCHEMA_FILENAMES` listed `critique_evaluator.json` but `schemas.SCHEMAS` didn't expose it.
- **~10h11m overnight idle** (23:38 → 09:49).
- **F4 (morning, in MAIN repo, 2h17m)** was a **manual `git merge --no-ff` of hardening-epic into main** — rebase conflicts, conflict resolution in `cli/parser.py` + `critique.py`, dep-gap fixes (`ulid`, `python-dotenv`), and validation to green (3153 passed / 29 skipped).

It mattered: because no review/gate phase ran, the F3 open test failure was carried silently across the overnight gap and only swept up incidentally during the manual merge. A `directed/light` review would have caught a red test before "done." The hard gate (collection parity) *did* do its job — and notably did so independent of review depth, exactly as the brief intended.

## 7 lenses

| Lens | Verdict | Evidence |
|---|---|---|
| 1. Blockers / dead-ends | MINOR | No crashes/resumes; 2 retries were dep installs (`ulid`, `python-dotenv`, F4:169). But the F3 open test failure was an unhandled dead-end carried 10h. [VERIFIED] |
| 2. Excessive revision | FINE | 0 review→rework cycles; work was linear. No re-flagging. (No pipeline to loop.) |
| 3. Low-value critiques | FINE | Critique never fired at runtime; `ADAPTIVE CRITIQUE FALLBACK` strings are source being merged, not invocations (F4:97). [VERIFIED] |
| 4. Model-tier mismatch | SIGNIFICANT | Orchestration ran **premium GPT-5 (Codex)** for mechanical conflict-resolution + a 5,300-line test split. Light/mechanical work that a cheaper driver could orchestrate; see #4 below. |
| 5. Repeated/bloated context | MINOR | ~97% cache hit (48.2M/49.6M cached) blunts cost, but F4 alone burned **39.2M input tokens** for a merge — natural file re-reads, no pathological re-send. |
| 6. Model confusion | FINE | No wrong-file edits or looping; agent correctly avoided ad-hoc env installs (F4:169) and protected sibling repos under `.megaplan-worktrees` (F4:1026). |
| 7. Inefficiency / waste | SIGNIFICANT | 13h22m span / ~3h54m active for a `light` cleanup + merge; 10h11m pure idle. Wall-clock wildly out of proportion to a low-risk diff. [VERIFIED] |

## Top 3 improvements

**1. The milestone never entered the harness — finish-by-hand defeated the chain's own gates. [DRIVING]**
*Problem:* `chain.yaml` declares m6b with critique/review/robustness, but the actual work was a manual Codex merge in the main repo; the declared config was inert.
*Root cause:* The hardening-epic branch was merged to main out-of-band instead of letting `megaplan chain` drive m6b to a gated, green close in the worktree.
*Fix:* Drive m6b's close through `megaplan auto`/`chain` in the worktree so the `directed/light` review + gate actually run; only merge after the gate passes green. Don't hand-merge mid-chain — it forks main's dirty state in (the known worktree-carry hazard) and skips the gate.

**2. F3 ended red and nobody noticed for 10h. [HARNESS]**
*Problem:* The execute session left `test_step_schema_filenames_reference_existing_schemas` failing and simply stopped; the failure survived the overnight gap.
*Root cause:* No post-execute gate/review fired to convert "execute finished" into "execute finished GREEN," so a red suite was treated as a stopping point. (Same family as the gate auto-downgrade and adaptive-critique-fallback findings — schema/`critique_evaluator` plumbing is fragile.)
*Fix:* Make the chain's per-milestone completion gate **hard-block on a green targeted suite** (here: the split modules) before marking done; surface red-at-stop loudly rather than idling. Add `critique_evaluator.json` to `schemas.SCHEMAS` so `STEP_SCHEMA_FILENAMES` parity can't desync (it bit M6b directly and overlaps the known evaluator-fallback bug).

**3. Premium GPT-5 orchestrated mechanical merge/split work. [DRIVING]**
*Problem:* 2h17m of premium GPT-5 on conflict resolution + a deterministic test-file split — the most mechanical milestone in the epic.
*Root cause:* `directed/light` here still routed the driving turns to the premium Codex model; nothing downgraded the *orchestration* tier for a light milestone.
*Fix:* For `robustness: light` milestones, route the orchestration/driving turns to a cheaper tier (the execute fan-out is already cheap DeepSeek). Reserve premium GPT-5.x for milestones whose plan/critique/review genuinely needs it. The ~97% cache hit shows the spend is mostly re-read context, not reasoning — a cheap driver would lose little.

---
**Adversarial check:** Claim "no pipeline ran, work was a manual merge" = [VERIFIED] (grep of F4: 3× `git merge --no-ff`, rebase conflict loops; 0 real `megaplan run/auto/chain` executions). Claim "10h11m overnight idle" = [VERIFIED] (F3 last event 2026-05-27T23:38:36 → F4 first 2026-05-28T09:49:17).
