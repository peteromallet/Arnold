# Pristine Cleanup — Megaplan Chain

A 6-milestone (+ publish) epic that takes VibeComfy to a structurally pristine
state, derived from a 10-agent structural audit of the repo (raw reports in
[`audit/`](audit/)).

## Why an epic
The audit findings cluster into four cross-cutting themes that independent
reviewers rediscovered separately, with hard dependencies between the fixes:

1. **No shared AST/graph util layer** → the same helpers copy-pasted 2–8× each.
2. **God-files** — `emitter.py` (3304 LOC), `session.py` (1379), `provider.py` (984).
3. **Three parallel implementations** of the same job — validation (×3, already
   diverged), eval-node (×3, a half-done migration), diagnostics (two systems).
4. **Docs that contradict the code** — `CLAUDE.md`/`AGENTS.md` byte-identical,
   documented loaders not actually importable, README on v2.6 vs CLAUDE on v2.7.

This is ~6–8 weeks across several architectural decisions that each deserve their
own brief + critique pass — epic-shaped, not single-sprint.

## The two principles driving the ordering
- **Repair the safety net first — and make the gate concrete.** The suite is not
  currently trustworthy (a broken import; `NotImplementedError` stubs in the public
  testing API; only ~4 of 9 declared parity fixtures exist). M1 fixes all of that and
  emits a re-runnable **golden gate** (`docs/audits/m1-safety-gate.md`: pytest + CLI JSON
  snapshots + import-surface + 9/9 parity) that every later milestone must pass.
  "Green pytest" alone is explicitly not the gate — both reviewers flagged that as the
  chain's biggest original hole.
- **Consolidate, then split.** Deduplicating (validation 3→1, eval 3→1) shrinks the
  god-files; M5 carves up already-smaller, deduplicated files. **Docs go last** so
  they describe the final state, not a moving target.

## Milestones

All milestones run `vendor: codex` (GPT-5.5 for the premium author slots).

| # | Milestone | Profile | Robustness | Depends on |
|---|---|---|---|---|
| M1 | Triage & safety net (tests fully green, parity fixtures 4→9, dead code gone, hygiene) | `premium` | full | — |
| M2 | Shared foundation layer (AST/graph/link utils — the kernel) | `apex` | thorough/high | M1 |
| M3 | Collapse schema/validation triad + decompose `provider.py` | `premium` | thorough/high | M2 |
| M4 | Collapse 3 eval modules + unify diagnostics | `premium` | full | M2 |
| M5a | Split `emitter.py` (3304 LOC) | `premium` | thorough/high | M2 (+M4 diag base) |
| M5b | Split `session.py` (1379 LOC) + fix error architecture | `premium` | thorough/high | M4 |
| M6 | Convention & API enforcement (**code only**) | `premium` | full | M2–M5 |
| M7 | Documentation reconciliation (**docs only**) | `directed` | full | M6 |
| — | publish-shared-branch (verify, RESULTS.md, push, open PR) | `solo` | light | all |

The chain runs sequentially, but the only real cross-dependency parallelism is
**M3 ∥ M5a** (the emitter does not import the validation triad) — exploitable in a
manual/cloud schedule if desired.

Each milestone hands the next a written artifact under `artifacts/`: M1 → duplication
inventory + golden-gate spec, M2 → symbol map, M6 → public-API surface (which M7 cites).

## Branch policy
Single accumulating branch, no per-milestone `branch:` fields; the final
`publish-shared-branch` milestone pushes once for a single human review.

**Before running, create the shared branch off the *clean* `main`** — not the
current in-progress `agentic-port-20260523` branch:

```bash
git branch megaplan/pristine-cleanup main
```

`merge_policy: review` keeps the human in the loop; `on_failure`/`on_escalate:
stop_chain` means a failing milestone halts the chain (correct for
behavior-preserving refactors — never skip-and-continue).

## Running

```bash
# Inspect the plan without driving anything.
megaplan chain status --spec docs/megaplan_chains/pristine_cleanup/chain.yaml

# Local, single-step (inspect each milestone before the next kicks off).
megaplan chain start --spec docs/megaplan_chains/pristine_cleanup/chain.yaml --one

# Drive the whole chain locally.
megaplan chain start --spec docs/megaplan_chains/pristine_cleanup/chain.yaml

# For a 6–8 week unattended run that outlives the terminal, use cloud chain mode
# with the relevant chain-local cloud config + the operator loop. See docs/cloud.md.
```

## The off-ramp
If "pristine" means "stop the bleeding" rather than full architectural cleanup,
**M1 alone is a single sprint** — it kills the confirmed bugs, dead code, and
hygiene issues and makes the suite trustworthy. Commit to M1+M2 at minimum (safety
net + the duplication root cause), then decide whether M3–M6 are worth it once you
see how much the god-files shrink.

## Source & revision history
- Raw per-lens audit reports: [`audit/01..10-*.md`](audit/)
- Generated 2026-05-23 from a 10-way DeepSeek-V4-Pro fan-out; HIGH-severity headline
  claims were spot-verified against the tree (one false positive — `port.py:611` is not
  corrupted — excluded).
- **Revised 2026-05-24** after an independent two-reviewer sense-check (Claude Opus +
  Codex/GPT-5.5), both verdict "ship with changes". Applied:
  - M1 hygiene corrected — **`template_index.json` is repo-owned and stays tracked**
    (the audit's lens-10 "untrack generated indexes" claim was wrong); `node_index.json`
    isn't tracked at all.
  - M1's "green or known-prior reds" escape hatch removed → **fully green + concrete
    golden gate**; the 4→9 parity-fixture backfill pulled forward into M1 (it gates M5a).
  - Old combined M5 **split into M5a (emitter, dep M2) + M5b (session/errors, dep M4)** —
    the emitter does not depend on M3/validation, so the original `M5→M2,M3,M4` DAG was
    overstated.
  - Old combined M6 **split into M6 (code conventions) + M7 (docs)**.
  - M7 drops the audit's false-positive "README dead skill path" claim —
    `docs/agent-skill/SKILL.md` **does** exist.
  - M1 tier raised `directed`→`premium` (the `template_index` near-miss shows M1 needs
    judgment). All milestones set to `vendor: codex`.
