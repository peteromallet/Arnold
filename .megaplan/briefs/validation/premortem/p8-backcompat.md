# P8 — Pre-mortem: backwards compatibility for existing state, config, packs, external callers

**Lens:** Working backward from a 6-months-later failure where the Pipeline-Unification
epic shipped and broke EXISTING usage: in-flight `.megaplan` plans that can't resume,
saved profiles/configs that stop working, a user's custom pack in `~/.megaplan/pipelines/`,
and downstream scripts/integrations that import `megaplan` or call the CLI.

Grounded in current code (2026-05-28), `__version__ = "0.23.0"`.

---

## Surfaces examined (evidence)

### A. State load / migrate path — `megaplan/_core/state.py`
- `load_plan_from_dir` (`:93-101`) sniffs **values** to decide migration:
  `current_state in {"clarified","evaluated"}` OR `"last_evaluation" in state` OR
  `"last_gate" not in state` → runs `write_plan_state(mode="legacy-migration")`.
- `_apply_legacy_state_migration` (`:293-308`) only handles the clarified/evaluated/
  last_evaluation/last_gate value renames. There is **no `schema_version` field** on
  `state.json` (C2 Claim 4 CONFIRMED) and **no structural validation on load** — only
  `current_state` is validated against `CANONICAL_PLAN_STATES` on *write*
  (`_validate_plan_state_for_persist`, `:248-263`, called `:433-434`).
- `read_json` (`io.py:272-273`) **raises** `JSONDecodeError` on corrupt content; several
  read callers (`load_plan_from_dir`, `PlanRepository.load_state`) get a bare traceback.

### B. Config / profiles / packs under `~/.megaplan` and `~/.config/megaplan`
- `config_dir` = `$XDG_CONFIG_HOME/megaplan` or `~/.config/megaplan`; `load_config`
  (`io.py:743-755`) is already tolerant — missing→`{}`, malformed→warn+`{}`, non-dict→`{}`.
  This surface is the **safest** today.
- Profiles: `config_dir(home)/profiles.toml` (user) + project `.megaplan/profiles.toml`
  (`profiles/__init__.py:472-479`). Validation is **hard-fail**: `_validate_profile_map`
  (`:272-281`) raises `CliError` for any phase key `not in VALID_PHASE_KEYS`; same for
  `tier_models.<phase>` (`:369-374`). `VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())`
  (`:24`) — i.e. **the planning phase names are the allowed set**.
- User packs: `discover_python_pipelines` (`registry.py:360-407`) scans
  `~/.megaplan/pipelines/`; a module needs a callable `build_pipeline`. Collisions with
  `_BUILTIN_NAMES = {"planning"}` (`:53`) are **skipped with a UserWarning** (`:382-389`).
- Registry home override: `MEGAPLAN_REGISTRY_HOME` (`tickets/registry.py:38-41`).

### C. Public `__all__` exports — handler API
- Top-level `megaplan/__init__.py:48-72` exports 17 `handle_*` (init, plan, critique,
  revise, gate, finalize, execute, review, step, status, audit, progress, list, override,
  setup, setup_global, config). `megaplan/handlers/__init__.py:75-90` exports 14
  (adds prep, audit_verifiability, verify_human, tiebreaker_run/decide).
- Every handler signature today is `(root: Path, args: argparse.Namespace)` (CLI dispatch
  `cli/__init__.py`). m5 migrates these to `(root, state, hctx)` — **a public signature
  break** for any caller doing `from megaplan import handle_execute` then calling it.

### D. External coupling (from s4)
- Cloud supervisor SSHes a **literal import string**:
  `from megaplan.chain import _capture_sync_state, ChainState, save_chain_state, load_chain_state`
  (`cloud/supervise.py:54`), executed remotely (`:257`). A rename/relocation of any of those
  four names = a remote-breaking change with **no static check**, and it breaks under
  **version skew** (new-operator/old-container or vice versa).
- 26 ambient `MEGAPLAN_*` env reads via bare `os.getenv` (no config bus). Renaming/relocating
  any toggle silently changes behavior per deployment.
- `megaplan status` JSON is consumed by cloud over SSH; not yet pinned by a contract test.

### E. Resume of a paused / in-flight plan
- A plan records its pipeline in `state["config"]["pipeline"]` (`init.py:226`,
  routing table `:47-52`). The human-gate pause writes `awaiting_user.json` with a
  `pipeline` field; `_resume_human_gate` (`cli/__init__.py:898,933`) does
  `get_pipeline(pipeline_name)` which **raises `KeyError`** for an unknown name
  (`registry.py:119-120`). If a pipeline is relocated/renamed/dropped from `_BUILTIN_NAMES`
  between write and resume, **resume hard-crashes**.

---

## Ranked break scenarios

### Scenario 1 — Half-finished plan resumed across the upgrade (state-shape skew)
**What:** A plan was written by old megaplan and is resumed after upgrade.
**Why:** m1 adds `schema_version` + a load-time validator. Today's plans have **no version
field**. If the validator is strict (rejects/fails on absent or unknown version) it will
reject every pre-epic plan. Conversely, a plan written by the *new* version (with
`dispatch_path`/`schema_version`) opened by a downgraded/old engine (cloud container lag)
hits unknown keys and the value-sniffing migration mis-fires.
**Milestone:** m1 (schema_version), aggravated by any later state-shape change (m3 resume
fields: `resume_cursor`, `_pipeline_paused_stage`).
**Severity:** HIGH — every in-flight plan at upgrade time.

### Scenario 2 — Resume of a plan created as the old built-in / relocated pipeline
**What:** Plan paused at a human_gate (or `state.config.pipeline`) referencing `"planning"`
(or `doc`/`creative`); m4 relocates planning to `megaplan/pipelines/planning/` and
**drops its `_BUILTIN_NAMES` entry**, making it discovery-dependent.
**Why:** `_resume_human_gate` does `get_pipeline("planning")` → `KeyError` if discovery
silently fails (the brief's own "discovery-integrity guard" risk) or if the name changed.
The discovery guard (m1) is exactly what must prevent a silent miss here.
**Milestone:** m4 (relocation + drop `_BUILTIN_NAMES`), guarded by m1.
**Severity:** HIGH — hard crash on resume; affects the dominant pack (planning).

### Scenario 3 — Saved profile referencing planning phase keys / new pack slots
**What:** A user's `~/.config/megaplan/profiles.toml` (or project `.megaplan/profiles.toml`)
maps planning phases. m2 decouples `VALID_PHASE_KEYS` from `DEFAULT_AGENT_ROUTING` so packs
declare their own slots.
**Why:** `_validate_profile_map`/`_validate_tier_models` **hard-fail** (`CliError`) on any
key not in the (now narrower or per-pack) `VALID_PHASE_KEYS`. If the decoupling tightens the
default set, existing profiles that named planning phases stop validating → every command
that loads a profile errors. tier_models has the same hard-fail surface.
**Milestone:** m2 (VALID_PHASE_KEYS decouple, `resolve_agent_mode` rewrite).
**Severity:** HIGH — breaks the user at CLI parse time for *all* commands, not just one pack.

### Scenario 4 — External caller imports `handle_*` and calls with the old signature
**What:** A downstream script does `from megaplan import handle_execute; handle_execute(root, args)`.
**Why:** m5 migrates `handle_*(root, args)` → `(root, state, hctx)`. These are in `__all__`
(public API). The epic notes "deprecation shims for the two public handler exports" — but
**17 are exported top-level and 14 from handlers**, not two. Any unshimmed handler raises
`TypeError`/missing-arg.
**Milestone:** m5 (HandlerContext).
**Severity:** MEDIUM-HIGH — silent for most users, fatal for integrators; surface is larger
than the epic's shim plan assumes.

### Scenario 5 — Cloud supervisor / version-skew over SSH
**What:** Operator upgrades local megaplan; remote container runs old (or vice versa). The
SSH `from megaplan.chain import _capture_sync_state, …` string mismatches the remote module.
**Why:** Internal names baked into a wire string with no static check (s4 Claim 1).
**Milestone:** m3 (re-point cloud coupling onto the pinned m1 status contract).
**Severity:** MEDIUM — affects cloud users; manifests as remote sync/status failures, not
local breakage.

### Scenario 6 — A user's custom pack in `~/.megaplan/pipelines/` breaks
**What:** A custom `build_pipeline` pack relied on planning being a built-in, on the old
`StepContext`/profile contract, or used a phase slot the new `resolve_agent_mode` rejects.
**Why:** m2 replaces bare `DEFAULT_AGENT_ROUTING[step]` with typed slot resolution; m6 adds
`capabilities` metadata and EvidenceRealizer injection. A pack written to the old contract
may dispatch wrong or fail to resolve a model.
**Milestone:** m2 / m6.
**Severity:** MEDIUM — narrow audience (pack authors), but it's the epic's headline use case
("any pack"), so a silent regression here is reputationally costly.

### Scenario 7 — Corrupt/edge state surfaces as a bare traceback on the new path
**What:** Pre-existing corrupt or hand-edited state hits the new load-time validator.
**Why:** `read_json` raises; new validator may raise rather than degrade. Existing behavior
is already loud-but-inconsistent (C2 Claim 6); a stricter m1 validator widens the blast.
**Milestone:** m1.
**Severity:** LOW-MEDIUM.

### Scenario 8 — CLI argument-contract drift breaks auto.py-style subprocess drivers
**What:** Any script (incl. auto.py before m3) drives megaplan via `python -m megaplan <args>`
(`auto.py:266,287`). m3's in-process port or any flag rename breaks the subprocess contract.
**Why:** auto.py rebuilds config from `state["config"]` per phase; m3 changes that boundary.
**Milestone:** m3.
**Severity:** LOW for users (auto.py is internal), MEDIUM if any user wraps the CLI per-phase.

---

## Required migration / deprecation guarantees the epic MUST add

1. **Versioned, forgiving state migration (m1).** `schema_version` MUST default-treat an
   ABSENT version as "v0/legacy" and run the existing value-sniff migration — never reject.
   The validator must *upgrade-and-persist*, not *fail-closed*, on old plans. Add a forward
   guard: a NEWER schema_version opened by an older engine must warn + best-effort, not crash.
   Add a state-migration test that loads a real pre-epic `state.json` fixture and resumes.
2. **Pipeline-name resolution must tolerate relocation (m4, guarded by m1).** Keep a
   name-alias map (old built-in/`_BUILTIN_NAMES` names → new discovered names) so
   `get_pipeline(name_from_state_or_awaiting_user)` never `KeyError`s for a name a prior
   version legitimately wrote. The m1 discovery-integrity guard must fail LOUD at startup if
   `planning` can't be discovered after relocation (not silently absent).
3. **Profile backward-compat (m2).** When `VALID_PHASE_KEYS` decouples, the planning pack's
   phase names MUST remain valid for profiles (don't tighten the default set out from under
   existing `profiles.toml`). Downgrade unknown-phase from hard `CliError` to a deprecation
   warning for a release, or auto-map legacy planning phase keys.
4. **Handler API deprecation shims for ALL `__all__` handlers, not two (m5).** Keep
   `(root, args)` callable via an `args_to_hctx` adapter behind the dispatch toggle for a full
   deprecation window; emit `DeprecationWarning`. Add an import-surface characterization test
   that pins the 17+14 exported `handle_*` names and their callable arity.
5. **Pin the cloud `status` JSON + `chain.py` import contract early (m1/m3).** Add a contract
   test for the `megaplan status` JSON and for the four `megaplan.chain` names the SSH string
   imports; on m3, re-point cloud onto the pinned contract and add a version-skew check
   (refuse/warn when remote and local `__version__` diverge).
6. **Env-var stability (m5).** Hoisting the 26 `MEGAPLAN_*` reads into HandlerContext must
   keep reading the existing names (no renames without an alias + deprecation window);
   characterize the 26 names in a test so a hoist can't silently drop one.
7. **chain_state.json gets schema_version + lock too (m1).** It currently has neither
   (C2 Claim 7) and is mutated remotely by the SSH path — same forgiving-migration guarantee.
