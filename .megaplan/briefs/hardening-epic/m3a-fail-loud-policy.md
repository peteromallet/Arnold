# M3a — Make failures loud: census + policy + low-risk visibility

**Rubric:** `partnered//high`, robustness `full`
**Position in epic:** milestone 3 of 12 (runs before M2). Depends on M1. **Front-loaded before the store work** — earlier visibility de-risks M2. This milestone takes a *complete census* of silent-failure sites, writes the raise/warn/emit policy, and applies only the *low-risk* visibility fixes; the strict halt/raise changes are M3b, after M1+M2.

## Outcome
A **complete, grep-driven census** of silent-failure sites in the hand-written core, classified in an authoritative raise/warn/emit **decision table**, plus the immediate low-risk subset of fixes (logging swallowed emitters, distinguishing missing-vs-corrupt reads) that make the store work safer.

## Scope (IN)
### Step 1 — BOUNDED CENSUS (changed per gap-hunt + Codex sense-check)
The original audit's enumerated list was **incomplete** — a 5-agent scope-hunt found ~15 more sites of the identical class in one pass. So the first deliverable is a census, not patching known lines. **But the census must be BOUNDED** (Codex A: a Codex grep dump showed `cloud/` alone has dozens of advisory excepts that must NOT be swept in). Rules:
- Prefer an **AST/scripted** pass (e.g. walk `ast` for `ExceptHandler` whose body is only `pass`/`continue`/`return <empty-default>`), not a raw eyeball grep.
- **Explicitly exclude**: `tests/`, generated files, `megaplan/agent/` (vendored), and `megaplan/cloud/**` + CLI-surface modules whose excepts are deliberate user-facing error reporting (`except CliError`, `print(...); return` patterns) — those are advisory, not silent state corruption.
- **Scope = the hand-written core's state/decision/persistence paths** (handlers, _pipeline engine, execute, orchestration, store reads, auto.py, _core). The test is "would a silent failure here corrupt state or mislead a decision?" — if it's just a logged CLI error, it's out.
- **Classify every in-scope hit** in the table, but **patch only the agreed low-risk class** in this milestone (the rest go to M3b). The table — not a sprawling patch — is the artifact.

Suggested commands (a starting point for the scripted census, not the whole method):
```
grep -rPn 'except[^:]*:\s*$' megaplan/ --include=*.py    # then inspect bodies for pass/continue/return-default
grep -rPn 'except.*:\s*(pass|continue)' megaplan/ --include=*.py
grep -rPn 'except.*:\s*return (set\(\)|\[\]|\{\}|None|False)' megaplan/ --include=*.py
grep -rPn 'print\(.*file=sys\.stderr' megaplan/ --include=*.py
```
across the hand-written core (exclude `megaplan/agent/`). Classify every hit. Known sites the census MUST include (audit + gap-hunt):
- **handlers** — `gate.py:528-542` (event emission); `critique.py:544-550` (`_validate_tiebreaker` silent TIEBREAKER→ITERATE); `gate.py:404-417` (`_prior_unresolved_flag_ids`); **`override.py:158,184,319,359,572,633`** (6× `emit(...) except: pass`) + **`override.py:777`** (profile-load swallow) + the two override actions (`_override_recover_blocked :517`, `_override_set_model :734`) that emit **no** event at all; **`verifiability.py:54-55`** (corrupt `human_verifications.json` → `[]`).
- **_pipeline** — `executor.py:124-126` (corrupt state.json discard + blind overwrite); **`stages/inprocess_step.py:126-127`** (JSONDecodeError → `{}` then merge-overwrite); **`faults.py:90-91`** (corrupt `faults.json` → empty); **`run_cli.py:323-328`** (OSError on state.json write).
- **execute** — **`core.py:761`** (snapshot fail → empty diff, corrupts scope-drift signal); **`core.py:828-829`** (corrupt batch artifact skipped → wrong prereq pass); **`quality.py:518-523`** (git snapshot fail → advisory string, gate degrades).
- **auto.py** — `:1194,1362,1546,1641,1985` (event emission); **`:380-381,:386-387`** (liveness glob/stat → false idle-timeout kill risk); **`:423-424`** (heartbeat corrupt-state degrade); **`:518-519`** (`_latest_versioned_artifact` → None feeds escalate decisions); **`:893-896` + caller `:1244`** (write-failure bool discarded).
- **chain.py** — `_warn_vendor_ignored_for_locked_profile :1518-1530` (profile-load + nested vendor-resolve swallow).
- **io / logging** — `_core/io.py:253-254`; logging inconsistency: raw `print(file=sys.stderr)` at `handlers/shared.py:152`, `auto.py:335` vs `logging.getLogger("megaplan")` (`shared.py:55`); **`finalize.py:27` uses `getLogger(__name__)`** not the `"megaplan"` logger.

### Step 2 — Low-risk fixes to APPLY now (de-risk M2)
- Log (WARNING, once) every swallowed observability-emission failure — best-effort but never invisible.
- Distinguish "no prior file / first run" (legitimately empty) from "corrupt/unreadable" (log loudly) at `_prior_unresolved_flag_ids` and the analogous `verifiability.py`/`faults.py`/`auto.py` read sites — **no happy-path behavior change**.
- Route phase notices / heartbeats through `logging`; fix `finalize.py` to use the `"megaplan"` logger.

### Deferred to M3b
State-corruption halts (`executor.py`/`inprocess_step.py`), the strict gate-downgrade signal, vendor-lock raise, `execute/core.py` corrupt-batch halt, `auto.py` write-failure halt — anything that changes control flow.

## Locked decisions
- **The census is exhaustive** — driven by grep, not a hand-list; the table covers every hit (including ones found beyond the examples above).
- Best-effort side effects stay best-effort but log ≥once at WARNING — never bare `pass`.
- One logging mechanism (`logging.getLogger("megaplan")`); reserve `print` for user-facing CLI stdout.
- The decision table is authoritative for M3b — M3b implements it, doesn't re-litigate.

## Open questions (for plan to resolve)
- Per site: raise vs warn vs emit?
- The grep-stable token for the tiebreaker downgrade signal (e.g. `TIEBREAKER_DOWNGRADED_MISSING_FIELDS`).
- Are the two emission-less override actions (`:517`,`:734`) a bug or an intentional omission? (document the answer)

## Constraints
- No new crash paths on legitimately-empty conditions (first-iteration missing files are normal).
- Low-risk fixes only here; control-flow changes are M3b.

## Done criteria
- A `docs/` decision table covering **every census hit** → raise/warn/emit + rationale + (for events) grep-stable token.
- Swallowed observability emitters log at WARNING; test asserts a forced emit failure logs.
- Missing-vs-corrupt distinguished at the read sites; test covers a corrupt-read case.
- `grep -rPn 'print\(.*file=sys\.stderr' megaplan/` returns nothing at the named sites; `finalize.py` uses the `"megaplan"` logger.
- M0 baselines green.

## Touchpoints
`docs/` (census + table), `megaplan/handlers/{gate,critique,override,verifiability,shared,finalize}.py`, `megaplan/_pipeline/{executor,faults,run_cli}.py` + `stages/inprocess_step.py`, `megaplan/execute/{core,quality}.py`, `megaplan/auto.py`, `megaplan/_core/io.py`, `tests/`.

## Anti-scope
- Do NOT apply control-flow-changing fixes — those are M3b.
- Do NOT redesign the observability subsystem or change event schemas/types.
- **Enforceable guardrail:** NO edits to `_phase_command`, `drive()` next-step selection, `workflow_next`/`infer_next_steps`, `loop/engine.py` dispatch, or chain↔auto coupling — only local error handling at census sites. A reviewer greps these symbols to confirm they're untouched.
