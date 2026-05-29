# Executability check — can this chain actually RUN as configured? (2026-05-29)

Every prior phase asked "is the design sound." This asks "can the harness self-drive this chain." Grounded
against the real `megaplan chain` CLI + the megaplan-epic skill + our `scratchpad-emitter.yaml`.

## 1. Seam consistency across the parallel-written briefs — RESOLVED, with one residual
The 9 way-through briefs were written in parallel; three handoff contracts were unverified at write time.
Reconciliation (now folded into the milestone files):
- **Identity field shape** — UNIFIED: `vibecomfy_uid = scope_path:local_uid`, frozen in M1.5 as the degrade
  case, extended (not replaced) in M2, consumed in M5. No disagreement remains.
- **The layout store** — UNIFIED: one `layout_store.py` envelope `{store_version, vibecomfy_version,
  schema_hash, entries}`; M2 builds it + GC/migrate, M5 reads it, M6 wires the CLI. Consistent.
- **Where conversion/oracle plugs in** — UNIFIED on the vendored ComfyUI (`comfy_backend.ensure_nodes()`):
  M2 (subgraph locator + expansion), M3 (convert_ui_to_api oracle + live object_info). Consistent.
- **RESIDUAL seam:** the `properties["vibecomfy"]` namespacing (Phase-D #2/#8) touches M2 (capture), M3
  (emit), M5 (match), M7 (route) — every milestone must agree on the exact sub-object schema. It's stated
  in all four but the precise key layout (`{uid, scope, disposition?}`) should be pinned in M2 as a frozen
  contract the others cite, exactly like the uid field. Action: add a one-paragraph "namespaced properties
  schema" lock to M2. (Low risk, but it's the one cross-milestone data contract not yet single-sourced.)

## 2. Config-vs-implementation — what the chain assumes the harness does
Checked against `megaplan chain --help` / `chain start --help`:
- **`merge_policy: review`** — our value. The skill documents `auto | manual`; we wrote `review`. **UNKNOWN
  whether `review` is a recognized value** — it may be ignored/rejected. ACTION: confirm valid values
  (`megaplan chain override --help` / source); if only `auto|manual`, change to `manual` (we want human
  review between milestones anyway — `merge_policy: review` was aspirational naming).
- **Auto-merge:** there is NO auto-merge flag in the CLI surface. `merge_policy: auto` (per the skill) drives
  branch/PR lifecycle, but actual PR merge to `main` is almost certainly NOT automatic — the chain refreshes
  the base branch before each milestone (`--no-git-refresh` to disable), which means **each milestone expects
  the PRIOR milestone's branch to already be merged into base**. So with `manual` merge, the chain HALTS
  between milestones awaiting a human merge — that is correct and desired here, but it means this is NOT a
  fire-and-forget run; it's 7 supervised hops.
- **Per-milestone oracles/gates (object_info, zod, layout-diff, real-ComfyUI bypass) are TO-BE-BUILT, not
  harness hooks.** The chain does not provide them; they are deliverables of M3/M5. This is fine but must be
  explicit: early milestones cannot be gated by gates that don't exist yet (see #3).
- **Parallel tracks: NOT SUPPORTED.** `chain start --one` drives "at most one pending milestone"; the chain
  is **strictly serial**. Our spec is serial (good) — but any mental model of "M4 and M7 in parallel" is
  invalid; they run in listed order.

## 3. Bootstrapping circularity — the chain builds the machinery it's judged by
This is the real subtle one. Several milestones are GATED BY machinery that EARLIER milestones build:
- M5's acceptance is the **layout-diff oracle** — but the oracle is itself an M5 deliverable. Fine (a
  milestone can build its own gate), but it can't be a *pre-existing* gate.
- M3 builds the **real ComfyUI oracle**; M2 lands before it. So **M2 cannot be verified by the independent
  oracle** — only by the (acknowledged self-referential) parity gate + manual review. That's acceptable for
  a foundation milestone IF we state it: M2's correctness rests on M1.5's end-to-end demo + cross-critic, not
  on a gate that doesn't exist yet.
- The `comfy_backend` boot module is needed by BOTH M2 (locator) and M3 (oracle). **It must be built in M2
  (or M1.5), not assumed.** Currently M2 lists it in scope — good. But M1.5's widget-count fix also wants
  `object_info_widget_order` from the snapshot (not the live backend) — so M1.5 does NOT depend on
  comfy_backend. Clean ordering: snapshot-based in M1.5/early, live-backend from M2 on.
- **No chicken-and-egg that blocks t0**, but the dependency is: comfy_backend (M2) → real oracle (M3) →
  everything M3+ is gated. If comfy_backend slips, the oracle slips, and M3-M7 lose their gate of record.

## 4. M0 / M1.5 executability — CAN the front actually run?
- **M0 is NOT a chain milestone** — it's a manual pre-step (the chain has no M0 entry; it's a comment block).
  Its blockers are real and OUTSIDE the chain: PR #26 retargeted to main, m3-seams-ir T1-T26 committed +
  merged, suite green. **The chain literally cannot start until M0 is done by hand** — `base_branch: main`
  must contain `contracts/ir.py`, which is currently uncommitted on a side branch. This is the #1 thing
  blocking "go." It is correctly flagged but it is a HARD manual gate, not something the chain resolves.
- **M1.5 executability:** the brief is concrete and self-contained (subject = a flat editor JSON; fix the
  widget assert; wire `--to ui`; capture+restore pos by uid; make the comfy_nodes entry point real). All
  touchpoints exist in code today. **One catch:** M1.5's acceptance includes a "real ComfyUI editor opens
  it" proof (Proof B/C) — that's a human/manual step, not an automated gate, so M1.5 cannot be fully
  auto-verified by the chain; the cross-critic + offline Proof A + Proof D (edit-invariance) are the
  automatable parts. Acceptable, but means M1.5 needs a human in the loop at its gate.

## 5. Sequencing re-check under these gaps
- The order is sound: M1.5 (skeleton, snapshot-gated) → M2 (identity + comfy_backend) → M3 (real oracle) →
  M4 (layout) → M5 (preserve + the headline gate) → M6 (productionize) → M7 (in-editor).
- **One adjustment to consider:** the comfy_backend boot + the real `convert_ui_to_api` oracle are so
  foundational (they de-risk M2's identity AND replace the self-referential gate) that pulling a *minimal*
  comfy_backend into M1.5 (just `ensure_nodes()` + one `convert_ui_to_api` smoke on the flat subject) would
  let even the skeleton be checked by the real oracle instead of the self-referential one. Costs little,
  retires the biggest "are we self-validating" risk at milestone one. Recommended.
- Nothing else needs reordering; the chain CAN self-drive serially once M0 is cleared — modulo the
  human-in-the-loop gates at M1.5 (editor-open) and M5 (visual review), which `merge_policy: manual` already
  implies.

## 6. Cost/time of what "go" commits to
- **Scope: 7 chain milestones** (not 14 — the "14" was the count of review LENSES, not milestones), tiers:
  2× premium (M2, M5), 4× partnered (M1.5, M3, M4, M7), 1× directed (M6). No apex/extreme — the heaviest are
  premium//thorough (M2) and premium//full (M5).
- **Each milestone is a full megaplan** (brief→plan→critique→execute→review), several with `critic: cross`
  (a second frontier model). At ~premium/partnered tiers this is a substantial token + wall-clock cost per
  milestone; two `critic: cross` milestones roughly double their review cost.
- **This is NOT a one-shot "go."** With `manual` merge + human gates at M1.5/M5, it's **7 supervised hops**
  over (realistically) weeks, each needing a PR review + merge before the next refreshes base. The honest
  framing: "go" commits to a multi-week, supervised, premium-tier epic — not an unattended overnight run.
- **Cheapest de-risking before committing the full spend:** run M1.5 ALONE first (`chain start --one`), prove
  the end-to-end loop + the real-ComfyUI oracle on one workflow, THEN commit to M2-M7. The walking skeleton
  was designed exactly for this — it's the cheap option that validates the expensive plan.

## DECISION (2026-05-29): merge_policy = auto, fully unattended. Consequence + fix.
The maintainer chose `merge_policy: auto` — the chain self-drives end to end, each milestone's PR
auto-merges into base, the next milestone refreshes base and builds on it. **This is the right call for
velocity, but it changes one hard requirement: EVERY milestone gate must be MACHINE-CHECKABLE.** Under
unattended auto-merge a human-in-the-loop gate either blocks the chain forever or (worse) is silently
skipped and the milestone auto-merges unverified. Two gates were written as human steps and MUST become
automated equivalents:

- **M1.5 "open in the real ComfyUI editor" (Proof B/C)** → replace the human eyeball with an AUTOMATED
  editor-open smoke: boot the vendored ComfyUI server (`comfy_backend`), POST the emitted `.json` through
  the load path (or run `convert_ui_to_api` on it), assert zero "node type not registered"/dangling-link
  errors. Proof A (pos round-trips offline) and Proof D (edit-invariance) are already automated. The
  real-editor human check becomes an OPTIONAL post-hoc confidence step, NOT the gate.
- **M5 "visual review reads cleanly" / "manual review" of layout** → the gate is the AUTOMATED **layout-diff
  oracle** (`max Δpos==0 ∧ Δsize==0` over uid-matched nodes) + the no-overlap invariant + the emit→re-emit
  ×N convergence test. The "looks hand-placed" human judgment becomes optional; the machine gate is the
  no-overlap + determinism + drift==0 trio. M4's "open looking sensible (manual review)" likewise leans on
  the no-overlap invariant as the actual gate.

This is consistent with the existing design — those automated gates already exist in the plan; we are just
making them THE gate of record rather than a human's eyeball, which auto-merge requires.

## Net: things to fix before "go"
1. **M0 is a hard manual prerequisite** (commit/merge m3-seams-ir, retarget PR #26, green suite). The chain
   cannot start until `base_branch: main` carries `contracts/ir.py`. Do this first, by hand. (This is the
   ONE manual step that remains even under full auto-merge — it's outside the chain.)
2. **`merge_policy: auto` is SET.** Unattended end to end. Therefore every milestone gate is machine-checkable
   (above) — no human-in-the-loop gates remain; the real-editor / "looks good" checks are optional post-hoc.
3. **Auto-merge raises the stakes on the gates themselves.** With no human between milestones, a milestone
   that auto-merges on a green-but-shallow gate poisons every downstream milestone (they refresh base from
   it). So the gates that auto-merge MUST be the real ones: M2/M3 verified by the live-ComfyUI oracle (not
   the self-referential parity gate), M5 by the layout-diff oracle. This makes the Phase-D "real oracle from
   vendored ComfyUI" non-optional — it is what makes unattended auto-merge safe. Pull a minimal
   `comfy_backend` into M1.5 so even the first auto-merged milestone is checked by the real oracle.
4. **Pin the `properties["vibecomfy"]` schema as a frozen contract in M2** (the one un-single-sourced
   cross-milestone seam). Still recommended: run M1.5 alone (`chain start --one`) before unleashing the full
   unattended run — one cheap supervised hop to confirm the loop + the real oracle, THEN let auto-merge fly.
