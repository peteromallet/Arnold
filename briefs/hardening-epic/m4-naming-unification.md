# M4 — Naming & vocabulary unification

**Rubric:** `directed//high +prep`, robustness `full`
**Position in epic:** milestone 6 of 12. Depends on M3b. **Must precede M5a/M5b** — rename intact files, then move code.

## Outcome
Resolve domain-vocabulary homonyms and synonym drift so a reader can tell what a term means without tracing call sites. Produce a canonical-vocabulary map (prep deliverable) and apply it — mostly as mechanical renames, with one item (gate_carry) handled as a deliberate data migration.

## Scope (IN)
- **"gate" homonym** — `handlers/gate.py:420` `handle_gate` (AI quality checkpoint) vs `_pipeline/steps/human_gate.py:23` `HumanGateStep` (pause-for-human). Disambiguate one.
- **"step" means three things** — `_pipeline/types.py:168` `Step` Protocol (pipeline node), `types.py:88` `ActiveStep` TypedDict, workflow phases called "steps" (`_PROGRESS_PHASE_COMMANDS`, `cli.py:113`); two dirs `_pipeline/steps/` vs `_pipeline/stages/`. **Per review: the real homonym is the inner TypedDict key — `state["active_step"]["step"]` (`types.py:88-89`)** — renaming the TypedDict alone doesn't fix callers reading the `"step"` key. Also decide the `stages/` vs `steps/` directory vocabulary here (physical rename, if any, deferred to M5b).
- **"verdict" homonym** — `handlers/review.py:383` `review_verdict`, `handlers/verifiability.py:71` `verdict` (pass/fail), `_pipeline/types.py:108` `Verdict` dataclass. Disambiguate. **Note `schemas/runtime.py:492` requires `"verdict"` as a schema key** — account for it.
- **`gate_carry` duplicate field — DATA MIGRATION, decision LOCKED.** `handlers/gate.py:248-252` writes both `verdict` and `recommendation` = the same value to `gate_carry.json`. **DECISION (verified): keep `recommendation`, DROP the duplicate `verdict`.** Rationale: the gate semantically emits a *recommendation* (PROCEED/ITERATE/ESCALATE); `gate.py:139` already reads `recommendation or verdict` (recommendation-first); `_sync_legacy_last_gate_for_workflow` (`:268-274`) copies `recommendation`. **Correcting the earlier review's premise:** `schemas/runtime.py:492`'s required `verdict` is the *sense_checks* field (review pass/fail) — a **different** `verdict`, itself an instance of the homonym this milestone documents — NOT a constraint on gate_carry. So dropping gate_carry's `verdict` violates no schema. Consumers to update: `prompts/execute.py:530` (`_gate_summary_or_skipped`) and **`prompts/_shared.py:46` (verified per Opus sense-check — the gate.json fallback path in `_gate_summary_or_skipped` *synthesizes* a `verdict` key alongside `recommendation`; the migration must drop it there too, or the back-compat read resurrects the duplicate)**. Add a back-compat read accepting `verdict` as fallback during transition; a test must cover prompt rendering after the key is gone (no existing test catches a `KeyError` inside AI prompt render). (Override the survivor choice at init if desired.)
- **Dead dispatch alias only (corrected per review).** `handlers/execute.py:9` aliases `handle_execute_auto_loop` as `dispatch_execute_auto_loop` — grep confirms **zero external imports**; remove the dead alias. **Do NOT unify `drive()` / `run_auto()` / `run_pipeline()` / `handle_execute_auto_loop()`** — they are *distinct concepts* (orchestration loop / CLI entry / pipeline executor / auto-execute handler) and need distinct names. The original "four verbs, one action" framing was wrong.
- **Constant-value mismatch** — `types.py:28` `STATE_AWAITING_HUMAN = "awaiting_human_verify"`. Rename the *constant* (callers use the name; `AUTOMATION_TERMINAL_STATES` at `:32` uses the constant) — **never** the string value (would break every on-disk `state.json`).
- **"critique" vs "review"** — `handlers/critique.py:66` vs `handlers/review.py:480`. Likely **document the pre/post invariant prominently** rather than rename (lower risk).
- **(Added per gap-hunt) `Backend` vs `HomeBackend` synonym drift** — `store/base.py:45` `Backend = Literal["file","db"]` and `schemas/base.py:30` `HomeBackend = Literal["file","db"]` are byte-identical types with different names (Store protocol uses one, Pydantic models the other). Pick one canonical alias, alias the other.
- **(Added per gap-hunt) `Plan.current_state: str` is unvalidated** (`schemas/sprint1.py:221`) despite the 18 canonical `STATE_*` constants in `types.py:13-30` — a misspelled state propagates silently to disk. **Ownership LOCKED: the *naming/vocabulary* decision (which constant is canonical, any renames) lives HERE; the *enforcement* (adding the `Literal`/validator — a behavior change) is owned by M2's validation pass.** Hand M2 the canonical state-string list as part of this milestone's output.

## Locked decisions
- Mostly rename/vocabulary (no behavior change, no file relocation = M5*) — **except `gate_carry`**, which is an explicit, tested data migration.
- The canonical-vocabulary map is the prep deliverable, locked before any rename.
- Persisted string values change ONLY with an explicit migration + back-compat read (applies to `gate_carry`). Prefer renaming the Python identifier over the persisted string everywhere else.
- Renames touch **identifiers only, not function signatures** (param names/types/order).

## Open questions (for prep + plan to resolve)
- Per homonym: which usage keeps the word, which gets renamed? (the map)
- For `gate_carry`: which of `verdict`/`recommendation` survives, given the 4 consumers + the `schemas/runtime.py` requirement?
- Is `critique`/`review` worth renaming, or is a documented invariant the lower-risk fix?

## Constraints
- Completeness is the risk — a partial rename is worse than none.
- Cross-format: renamed identifiers may appear in `.py`, `.json`, `.md`, `.yaml`, and schema definitions.

## Done criteria
- Canonical-vocabulary map in `docs/` (term → meaning → identifier).
- Each homonym resolved with distinct identifiers; the dead `dispatch_execute_auto_loop` alias removed (grep-verified).
- `gate_carry` migration: a test deserializes `gate_carry.json` and asserts exactly one of `verdict`/`recommendation` exists post-migration, AND all 4 consumers handle the new shape (incl. a prompt-render smoke test).
- **Cross-format grep** for each renamed identifier (`.py`/`.json`/`.md`/`.yaml`) returns no stale references; explicit patterns listed in the plan.
- M0 baselines green (CLI parser snapshot + goldens updated only where intended).

## Touchpoints
`megaplan/handlers/{gate,review,critique,verifiability,execute}.py`, `megaplan/execute/core.py`, `megaplan/_pipeline/types.py`, `_pipeline/steps/`, `_pipeline/stages/`, `megaplan/types.py`, `megaplan/schemas/runtime.py`, `prompts/execute.py`, `prompts/_shared.py`, `megaplan/auto.py`, `chain.py`, `cli.py`.

## Step order (per review)
Dead alias removal (zero risk) → "gate" homonym → "verdict"/`gate_carry` migration (persisted) → `STATE_AWAITING_HUMAN` → critique/review (likely document-only) last.

## Anti-scope
- Do NOT move or split files (M5*). Rename in place; the `stages/`/`steps/` physical rename is M5b.
- Do NOT change function signatures, error handling (M3*), or store routing (M2).
- Do NOT rename resolution-domain identifiers canonicalized in M1.
- **Guardrail:** do NOT normalize "next-step" resolution or merge the drive engines.
